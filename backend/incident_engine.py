# backend/incident_engine.py

import os
import datetime as dt
from typing import Dict, Any, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, Json

DB_DSN = os.getenv(
    "DATABASE_URL",
    "dbname=prismalite user=postgres password=postgres host=localhost",
)


class IncidentEngine:
    def __init__(self, dsn: str = DB_DSN):
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    # ===== ПУБЛИЧНЫЙ ВХОД =====

    def run_for_period(self, date_from: dt.datetime, date_to: dt.datetime) -> None:
        """
        Создаёт инциденты на основе событий за период.
        """
        with self._connect() as conn, conn.cursor() as cur:
            # 1. Берём события за период и сразу подтягиваем чек
            cur.execute(
                """
                SELECT
                    e.id            AS event_id,
                    e.receipt_id    AS receipt_id,
                    e.event_type    AS event_type,
                    e.severity      AS event_severity,
                    r.shop          AS shop,
                    r.cash          AS cash,
                    r.shift         AS shift,
                    r.number        AS number,
                    r.sale_time     AS sale_time
                FROM events e
                JOIN receipts r ON r.id = e.receipt_id
                WHERE e.created_at >= %s
                  AND e.created_at < %s
                ORDER BY e.receipt_id, e.id
                """,
                (date_from, date_to),
            )
            rows = cur.fetchall()

            # 2. Группируем по receipt_id
            events_by_receipt: Dict[int, List[Dict[str, Any]]] = {}
            for row in rows:
                rid = row["receipt_id"]
                events_by_receipt.setdefault(rid, []).append(row)

            # 3. Обработка каждой группы
            for receipt_id, events in events_by_receipt.items():
                self._ensure_incident_for_receipt(conn, receipt_id, events)

    # ===== ЛОГИКА СОЗДАНИЯ ИНЦИДЕНТА =====

    def _ensure_incident_for_receipt(
        self,
        conn,
        receipt_id: int,
        events: List[Dict[str, Any]],
    ) -> None:
        """
        Если по чеку ещё нет инцидента — создаём.
        Если инцидент уже существует — пока ничего не делаем (в будущем можно обновлять).
        """
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM incidents WHERE receipt_id = %s",
                (receipt_id,),
            )
            row = cur.fetchone()
            if row:
                # инцидент уже есть, пока не трогаем
                return

            # 1. Определяем severity A/B/C
            severity = self._calc_severity(events)

            # 2. Сводка по событиям
            event_types = sorted({e["event_type"] for e in events})
            events_count = len(events)

            # 3. Берём общие поля чека (shop/cash/shift/number/sale_time)
            any_event = events[0]
            shop = any_event.get("shop")
            cash = any_event.get("cash")
            shift = any_event.get("shift")
            number = any_event.get("number")
            sale_time = any_event.get("sale_time")

            # 4. Опционально — подсказка по видео (пока просто +/- 2 минуты от sale_time)
            video_from = None
            video_to = None
            video_meta = {}
            if sale_time:
                # sale_time уже с таймзоной, берём вокруг
                video_from = sale_time - dt.timedelta(minutes=2)
                video_to = sale_time + dt.timedelta(minutes=2)
                video_meta = {
                    "hint": "auto-range +/- 2 min from sale_time",
                }

            # 5. Создаём инцидент
            cur.execute(
                """
                INSERT INTO incidents (
                    receipt_id,
                    severity,
                    shop, cash, shift, number, sale_time,
                    event_types, events_count,
                    video_from, video_to, video_meta
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s)
                RETURNING id
                """,
                (
                    receipt_id,
                    severity,
                    shop, cash, shift, number, sale_time,
                    event_types, events_count,
                    video_from, video_to, Json(video_meta),
                ),
            )
            incident_id = cur.fetchone()[0]

            # 6. Заполняем связку incident_events
            for e in events:
                cur.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (incident_id, e["event_id"]),
                )

        conn.commit()

    def _calc_severity(self, events: List[Dict[str, Any]]) -> str:
        """
        A, если есть хоть одно событие A;
        иначе B, если есть B;
        иначе C (если только С или пустой набор).
        """
        severities = {e["event_severity"] for e in events}
        if "A" in severities:
            return "A"
        if "B" in severities:
            return "B"
        # если до сюда дошли — либо только C, либо вообще пусто
        return "C"

    # ===== ВСПОМОГАТЕЛЬНЫЙ ЗАПУСК =====

    def run_for_all_events(self) -> None:
        """
        Разовый прогон по всем событиям в БД.
        Удобно для инициализации после загрузки/миграции.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MIN(created_at), MAX(created_at) FROM events"
            )
            row = cur.fetchone()
            if not row or not row[0] or not row[1]:
                print("[WARN] no events in DB")
                return

            date_from, date_to = row[0], row[1]
            print(f"[INFO] Running IncidentEngine from {date_from} to {date_to}")
            self.run_for_period(date_from, date_to)
            print("[INFO] Done")


if __name__ == "__main__":
    engine = IncidentEngine()

    # Пока событий нет — этот запуск просто отработает вхолостую.
    # Когда появятся события (events), можно:
    # 1) либо гонять по последнему часу:
    now = dt.datetime.now(dt.timezone.utc)
    date_to = now
    date_from = now - dt.timedelta(minutes=60)
    print(f"[INFO] Running IncidentEngine from {date_from} to {date_to}")
    engine.run_for_period(date_from, date_to)
    print("[INFO] Done")

    # 2) либо один раз прогнать по всем:
    # engine.run_for_all_events()
