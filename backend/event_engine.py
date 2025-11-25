# backend/event_engine.py

import os
import datetime as dt
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# DSN: лучше потом заменить на тот, что уже используешь в проекте (из .env / docker-compose)
DB_DSN = os.getenv(
    "DATABASE_URL",
    "dbname=prismalite user=postgres password=postgres host=localhost",
)


class EventEngine:
    def __init__(self, dsn: str = DB_DSN):
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    # ===== ПУБЛИЧНЫЕ ВХОДЫ =====

    def run_for_period(self, date_from: dt.datetime, date_to: dt.datetime) -> None:
        """
        Основной запуск: пройтись по чекам за период и сгенерировать события.
        Это можно дергать из cron / systemd-таймера.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.*
                FROM receipts r
                WHERE r.sale_time >= %s
                  AND r.sale_time < %s
                ORDER BY r.sale_time
                """,
                (date_from, date_to),
            )
            receipts = cur.fetchall()

            for receipt in receipts:
                self.process_receipt(conn, receipt)

    def run_for_receipt(self, receipt_id: int) -> None:
        """
        Вспомогательный метод:
        пересчитать события для одного чека по id.
        Удобно для отладки.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM receipts WHERE id = %s", (receipt_id,))
            receipt = cur.fetchone()
            if not receipt:
                print(f"[WARN] receipt {receipt_id} not found")
                return
            self.process_receipt(conn, receipt)

    # ===== ОСНОВНАЯ ЛОГИКА =====

    def process_receipt(self, conn, receipt: Dict[str, Any]) -> None:
        """
        Обработка одного чека:
        - читаем позиции
        - прогоняем через набор правил
        - пишем события в events
        """
        receipt_id = receipt["id"]

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*
                FROM receipt_positions p
                WHERE p.receipt_id = %s
                ORDER BY p.id
                """,
                (receipt_id,),
            )
            positions = cur.fetchall()

        events: List[Dict[str, Any]] = []

        # --- Правила на чек ---
        events.extend(self._rule_return(receipt))

        # --- Правила на позиции ---
        for pos in positions:
            events.extend(self._rule_void(pos))
            events.extend(self._rule_manual_price(pos))
            events.extend(self._rule_weight_anomaly(pos))
            events.extend(self._rule_no_scan_sale(pos))
            events.extend(self._rule_discount_over_limit(pos))

        self._insert_events(conn, receipt_id, events)

    # ===== ПРАВИЛА =====

    def _rule_void(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        VOID — удалённая позиция.
        Сейчас: считаем void, если count <= 0 или есть is_void.
        Поля подгони под свою схему (is_void, count и т.д.).
        """
        events: List[Dict[str, Any]] = []

        is_void = bool(pos.get("is_void")) or (pos.get("count") is not None and pos.get("count") <= 0)

        if is_void:
            events.append({
                "event_type": "VOID",
                "severity": "B",
                "position_id": pos["id"],
                "details": {
                    "rule": "VOID",
                    "reason": "position_marked_void_or_zero_count",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                    "cost": pos.get("cost"),
                },
            })
        return events

    def _rule_return(self, receipt: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        RETURN — чек возврата.
        В JSON у тебя было operation_type: true/false.
        """
        events: List[Dict[str, Any]] = []

        operation_type = receipt.get("operation_type")

        if operation_type is False:
            events.append({
                "event_type": "RETURN",
                "severity": "B",
                "position_id": None,
                "details": {
                    "rule": "RETURN",
                    "amount": receipt.get("amount"),
                    "shop": receipt.get("shop"),
                    "cash": receipt.get("cash"),
                    "shift": receipt.get("shift"),
                    "number": receipt.get("number"),
                },
            })
        return events

    def _rule_manual_price(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        MANUAL_PRICE — ручная цена.
        insert_type = 2 (или аналог) — нужно будет подстроить под реальное поле.
        """
        events: List[Dict[str, Any]] = []

        if pos.get("insert_type") == 2:
            events.append({
                "event_type": "MANUAL_PRICE",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "MANUAL_PRICE",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                    "price": pos.get("cost"),
                },
            })
        return events

    def _rule_weight_anomaly(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        WEIGHT_ANOMALY — аномалия по весу.
        Требуются поля: is_weight, weight, cost, amount.
        Если их нет — правило тихо ничего не создаёт.
        """
        events: List[Dict[str, Any]] = []

        if not pos.get("is_weight", False):
            return events

        weight = float(pos.get("weight") or 0)
        unit_price = float(pos.get("cost") or 0)
        line_amount = float(pos.get("amount") or 0)
        calc_amount = weight * unit_price
        tolerance = 5.0  # TODO: вынести в настройки

        if weight == 0 or abs(calc_amount - line_amount) > tolerance:
            events.append({
                "event_type": "WEIGHT_ANOMALY",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "WEIGHT_ANOMALY",
                    "weight": weight,
                    "unit_price": unit_price,
                    "line_amount": line_amount,
                    "calc_amount": calc_amount,
                    "tolerance": tolerance,
                },
            })
        return events

    def _rule_no_scan_sale(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        NO_SCAN_SALE — продажа без сканера.
        Нужен флаг manual_entry / input_mode.
        Если его нет — правило не срабатывает.
        """
        events: List[Dict[str, Any]] = []

        manual_entry = bool(pos.get("manual_entry"))

        if manual_entry:
            events.append({
                "event_type": "NO_SCAN_SALE",
                "severity": "B",
                "position_id": pos["id"],
                "details": {
                    "rule": "NO_SCAN_SALE",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                },
            })
        return events

    def _rule_discount_over_limit(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        DISCOUNT_OVER_LIMIT — скидка выше лимита.
        Требуются discount_percent / discount_amount, иначе просто ничего не делаем.
        """
        events: List[Dict[str, Any]] = []

        discount_percent = float(pos.get("discount_percent") or 0)
        discount_amount = float(pos.get("discount_amount") or 0)

        limit_percent = 20.0   # TODO: вынести в БД
        limit_amount = 1000.0  # TODO: вынести в БД

        if discount_percent > limit_percent or discount_amount > limit_amount:
            events.append({
                "event_type": "DISCOUNT_OVER_LIMIT",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "DISCOUNT_OVER_LIMIT",
                    "discount_percent": discount_percent,
                    "limit_percent": limit_percent,
                    "discount_amount": discount_amount,
                    "limit_amount": limit_amount,
                },
            })
        return events

    # ===== ЗАПИСЬ В БД =====

    def _insert_events(
        self,
        conn,
        receipt_id: int,
        events: List[Dict[str, Any]],
    ) -> None:
        if not events:
            return

        with conn.cursor() as cur:
            for ev in events:
                pos_id: Optional[int] = ev["position_id"]

                # Простая защита от дублей:
                cur.execute(
                    """
                    SELECT 1
                    FROM events
                    WHERE receipt_id = %s
                      AND COALESCE(position_id, -1) = COALESCE(%s, -1)
                      AND event_type = %s
                      AND details = %s::jsonb
                    """,
                    (receipt_id, pos_id, ev["event_type"], Json(ev["details"])),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO events (receipt_id, position_id, event_type, severity, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        receipt_id,
                        pos_id,
                        ev["event_type"],
                        ev["severity"],
                        Json(ev["details"]),
                    ),
                )

        conn.commit()


if __name__ == "__main__":
    engine = EventEngine()

    # пример: обработать последние 60 минут по sale_time
    now = dt.datetime.now(dt.timezone.utc)
    date_to = now
    date_from = now - dt.timedelta(minutes=60)

    print(f"[INFO] Running EventEngine from {date_from} to {date_to}")
    engine.run_for_period(date_from, date_to)
    print("[INFO] Done")
