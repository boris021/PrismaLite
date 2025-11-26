import sys
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import Json

# ⚙️ Подключение к БД — так же, как в event_engine.py
DB = {
    "host": "localhost",
    "dbname": "prismalite",
    "user": "postgres",
    "password": "postgres",  # ← если у тебя другой пароль — поменяй
}

# Приоритет severity (A > B > C)
SEVERITY_ORDER = {
    "A": 3,
    "B": 2,
    "C": 1,
}


def get_connection():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    return conn


def fetch_events_for_period(cur, hours: int = 24):
    """
    Забираем события за последние N часов вместе с данными чека
    (shop, cash, shift, number, sale_time) — чтобы заполнить incidents.
    """
    cur.execute(
        """
        SELECT
            e.id          AS event_id,
            e.receipt_id  AS receipt_id,
            e.position_id AS position_id,
            e.event_type  AS event_type,
            e.severity    AS severity,
            e.created_at  AS created_at,
            e.details     AS details,
            r.shop        AS shop,
            r.cash        AS cash,
            r.shift       AS shift,
            r.number      AS number,
            r.sale_time   AS sale_time
        FROM events e
        JOIN receipts r ON r.id = e.receipt_id
        WHERE e.created_at >= now() - (%s || ' hours')::interval
        ORDER BY e.receipt_id, e.created_at, e.id;
        """,
        (hours,),
    )
    return cur.fetchall()


def merge_event_types(existing: List[str], new_types: List[str]) -> List[str]:
    """
    Объединяем старые и новые event_types без дублей.
    """
    s = set(existing or [])
    for t in new_types:
        if t:
            s.add(t)
    return sorted(s)


def get_or_create_incident(
    cur,
    receipt_id: int,
    best_severity: str,
    event_types: List[str],
    events_count: int,
    meta: Dict[str, Any],
):
    """
    Работаем с твоей схемой incidents (из \d incidents):

      id, receipt_id, severity, status,
      created_at, updated_at,
      shop, cash, shift, number, sale_time,
      event_types text[], events_count int,
      video_from, video_to, video_meta jsonb

    UNIQUE (receipt_id) → один инцидент на чек.
    """
    cur.execute(
        """
        SELECT id, severity, status, event_types, events_count
        FROM incidents
        WHERE receipt_id = %s
        LIMIT 1;
        """,
        (receipt_id,),
    )
    row = cur.fetchone()

    shop = meta.get("shop")
    cash = meta.get("cash")
    shift = meta.get("shift")
    number = meta.get("number")
    sale_time = meta.get("sale_time")

    if row:
        incident_id, old_severity, status, existing_event_types, existing_count = row

        # Обновляем severity, если новый хуже (A > B > C)
        final_severity = old_severity
        if (
            old_severity in SEVERITY_ORDER
            and best_severity in SEVERITY_ORDER
            and SEVERITY_ORDER[best_severity] > SEVERITY_ORDER[old_severity]
        ):
            final_severity = best_severity

        merged_types = merge_event_types(existing_event_types or [], event_types)
        # events_count логичнее хранить как реальное число событий по чеку
        total_count = events_count

        cur.execute(
            """
            UPDATE incidents
            SET severity     = %s,
                shop         = %s,
                cash         = %s,
                shift        = %s,
                number       = %s,
                sale_time    = %s,
                event_types  = %s,
                events_count = %s
            WHERE id = %s;
            """,
            (
                final_severity,
                shop,
                cash,
                shift,
                number,
                sale_time,
                merged_types,
                total_count,
                incident_id,
            ),
        )

        return incident_id

    # Инцидента ещё нет — создаём
    cur.execute(
        """
        INSERT INTO incidents (
            receipt_id,
            severity,
            shop,
            cash,
            shift,
            number,
            sale_time,
            event_types,
            events_count
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (
            receipt_id,
            best_severity,
            shop,
            cash,
            shift,
            number,
            sale_time,
            event_types,
            events_count,
        ),
    )
    (incident_id,) = cur.fetchone()
    return incident_id


def relink_incident_events(cur, incident_id: int, event_ids: List[int]):
    """
    Полностью пересобираем связи incident_events для указанного инцидента.
    """
    cur.execute(
        "DELETE FROM incident_events WHERE incident_id = %s;",
        (incident_id,),
    )

    if not event_ids:
        return

    cur.executemany(
        """
        INSERT INTO incident_events (incident_id, event_id)
        VALUES (%s, %s);
        """,
        [(incident_id, eid) for eid in event_ids],
    )


def run_incident_engine(hours: int = 24):
    """
    Основной запуск IncidentEngine:
    - забираем события за последние N часов
    - группируем по receipt_id
    - создаём/обновляем инциденты
    - пересобираем incident_events
    """
    conn = get_connection()
    cur = conn.cursor()

    print(f"[INFO] Running IncidentEngine for last {hours} hours...")

    rows = fetch_events_for_period(cur, hours=hours)
    print(f"[INFO] Loaded {len(rows)} events")

    if not rows:
        cur.close()
        conn.close()
        print("[INFO] No events found, nothing to do")
        return

    events_by_receipt: Dict[int, List[Dict[str, Any]]] = {}
    meta_by_receipt: Dict[int, Dict[str, Any]] = {}

    for row in rows:
        (
            event_id,
            receipt_id,
            position_id,
            event_type,
            severity,
            created_at,
            details,
            shop,
            cash,
            shift,
            number,
            sale_time,
        ) = row

        events_by_receipt.setdefault(receipt_id, []).append(
            {
                "id": event_id,
                "position_id": position_id,
                "event_type": event_type,
                "severity": severity,
                "created_at": created_at,
                "details": details,
            }
        )

        if receipt_id not in meta_by_receipt:
            meta_by_receipt[receipt_id] = {
                "shop": shop,
                "cash": cash,
                "shift": shift,
                "number": number,
                "sale_time": sale_time,
            }

    print(f"[INFO] Grouped into {len(events_by_receipt)} receipts")

    for receipt_id, ev_list in events_by_receipt.items():
        # 1. находим максимальный severity
        best_severity = None
        for ev in ev_list:
            sev = ev["severity"]
            if sev not in SEVERITY_ORDER:
                continue
            if (
                best_severity is None
                or SEVERITY_ORDER[sev] > SEVERITY_ORDER.get(best_severity, 0)
            ):
                best_severity = sev

        if best_severity is None:
            print(f"[WARN] receipt {receipt_id}: no valid severity, skip")
            continue

        # 2. список типов событий и количество
        event_types = sorted({ev["event_type"] for ev in ev_list if ev["event_type"]})
        events_count = len(ev_list)
        meta = meta_by_receipt.get(receipt_id, {})

        # 3. создаём/обновляем инцидент
        incident_id = get_or_create_incident(
            cur,
            receipt_id=receipt_id,
            best_severity=best_severity,
            event_types=event_types,
            events_count=events_count,
            meta=meta,
        )

        # 4. пересобираем связи incident_events
        event_ids = [ev["id"] for ev in ev_list]
        relink_incident_events(cur, incident_id, event_ids)

        print(
            f"[INFO] receipt {receipt_id}: incident {incident_id} "
            f"severity={best_severity}, events={len(event_ids)}"
        )

    cur.close()
    conn.close()
    print("[INFO] IncidentEngine finished")


if __name__ == "__main__":
    # Простой CLI:
    #   python incident_engine.py        → за последние 24 часа
    #   python incident_engine.py 1      → за последний 1 час
    hours = 24
    if len(sys.argv) >= 2:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            pass

    run_incident_engine(hours=hours)
