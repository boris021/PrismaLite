from typing import Optional, Dict, Any
from datetime import datetime

from .connection import get_connection, jsonb


def get_or_create_store(cur, store_code: str) -> int:
    cur.execute(
        """
        INSERT INTO prismalite.stores (code, name)
        VALUES (%s, %s)
        ON CONFLICT (code)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (store_code, store_code),
    )
    store_id = cur.fetchone()[0]
    return store_id


def get_or_create_till(cur, store_id: int, till_code: str) -> int:
    cur.execute(
        """
        INSERT INTO prismalite.tills (store_id, code)
        VALUES (%s, %s)
        ON CONFLICT (store_id, code)
        DO UPDATE SET code = EXCLUDED.code
        RETURNING id
        """,
        (store_id, till_code),
    )
    till_id = cur.fetchone()[0]
    return till_id


def get_or_create_cashier(cur, external_id: Optional[str]) -> Optional[int]:
    if not external_id:
        return None

    cur.execute(
        """
        INSERT INTO prismalite.cashiers (external_id)
        VALUES (%s)
        ON CONFLICT (external_id)
        DO NOTHING
        """,
        (external_id,),
    )

    cur.execute(
        """
        SELECT id FROM prismalite.cashiers
        WHERE external_id = %s
        """,
        (external_id,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_event_type_id(cur, event_code: int) -> int:
    cur.execute(
        """
        SELECT id FROM prismalite.event_types
        WHERE code = %s
        """,
        (event_code,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown event_code={event_code} (нет записи в event_types)")
    return row[0]


def insert_event(edr: Dict[str, Any]) -> int:
    """
    Принимает один EDR-словарь и вставляет строку в prismalite.events.
    Возвращает id созданного события.
    """
    store_block = edr.get("store") or {}
    till_block = edr.get("till") or {}
    cashier_block = edr.get("cashier") or {}
    event_block = edr.get("event") or {}
    receipt_block = edr.get("receipt") or {}
    payload = edr.get("payload") or {}
    raw_block = edr.get("raw") or {}

    store_code = store_block.get("code")
    if not store_code:
        raise ValueError("store.code is required")

    till_code = till_block.get("code")
    if not till_code:
        raise ValueError("till.code is required")

    event_code = event_block.get("code")
    occurred_at = event_block.get("occurred_at")
    if event_code is None:
        raise ValueError("event.code is required")
    if occurred_at is None:
        raise ValueError("event.occurred_at is required")

    # Приводим occurred_at к datetime
    if isinstance(occurred_at, str):
        # FastAPI/Pydantic может сам конвертировать, но здесь для надёжности
        occurred_at_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    elif isinstance(occurred_at, datetime):
        occurred_at_dt = occurred_at
    else:
        raise ValueError("event.occurred_at must be ISO8601 string or datetime")

    cashier_external_id = cashier_block.get("external_id")

    raw_source = raw_block.get("source", "pos")
    if raw_source not in ("pos", "agent", "system", "other"):
        raw_source = "agent"

    raw_line = raw_block.get("line")
    correlation_id = receipt_block.get("number")  # временно используем номер чека как correlation_id

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                store_id = get_or_create_store(cur, store_code)
                till_id = get_or_create_till(cur, store_id, till_code)
                cashier_id = get_or_create_cashier(cur, cashier_external_id)
                event_type_id = get_event_type_id(cur, int(event_code))

                cur.execute(
                    """
                    INSERT INTO prismalite.events (
                        store_id,
                        till_id,
                        cashier_id,
                        receipt_id,
                        event_type_id,
                        event_code,
                        source,
                        occurred_at,
                        payload,
                        raw_line,
                        correlation_id
                    )
                    VALUES (
                        %s, %s, %s, NULL,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        store_id,
                        till_id,
                        cashier_id,
                        event_type_id,
                        int(event_code),
                        raw_source,
                        occurred_at_dt,
                        jsonb(payload),
                        raw_line,
                        correlation_id,
                    ),
                )
                event_id = cur.fetchone()[0]
        return event_id
    finally:
        conn.close()
