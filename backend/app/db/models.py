from typing import Optional, Dict, Any, List
from datetime import datetime, date

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


def parse_iso_datetime(value: Any) -> datetime:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"invalid datetime: {value!r}")


def parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"invalid date: {value!r}")


# ============================
#  ВСТАВКА СОБЫТИЯ
# ============================

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

    occurred_at_dt = parse_iso_datetime(occurred_at)

    cashier_external_id = cashier_block.get("external_id")

    raw_source = raw_block.get("source", "pos")
    if raw_source not in ("pos", "agent", "system", "other"):
        raw_source = "agent"

    raw_line = raw_block.get("line")
    correlation_id = receipt_block.get("number")  # используем номер чека

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


# ============================
#  ВСТАВКА ЧЕКА + ПОЗИЦИЙ
# ============================

def insert_receipt_with_items(edr_receipt: Dict[str, Any]) -> int:
    """
    Принимает структуру чека (см. JSON формат) и создаёт:
    - запись в prismalite.receipts
    - записи в prismalite.receipt_items
    - линкует events.receipt_id по store/till/receipt.number
    Возвращает id чека.
    """
    store_block = edr_receipt.get("store") or {}
    till_block = edr_receipt.get("till") or {}
    cashier_block = edr_receipt.get("cashier") or {}
    receipt_block = edr_receipt.get("receipt") or {}

    store_code = store_block.get("code")
    if not store_code:
        raise ValueError("store.code is required")

    till_code = till_block.get("code")
    if not till_code:
        raise ValueError("till.code is required")

    receipt_number = receipt_block.get("number")
    if not receipt_number:
        raise ValueError("receipt.number is required")

    operation_type = receipt_block.get("operation_type", "SALE")
    business_date = parse_iso_date(receipt_block.get("business_date"))
    opened_at = parse_iso_datetime(receipt_block.get("opened_at")) if receipt_block.get("opened_at") else None
    closed_at = parse_iso_datetime(receipt_block.get("closed_at")) if receipt_block.get("closed_at") else None
    total_amount = receipt_block.get("total_amount")

    items: List[Dict[str, Any]] = receipt_block.get("items") or []
    cashier_external_id = cashier_block.get("external_id")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                store_id = get_or_create_store(cur, store_code)
                till_id = get_or_create_till(cur, store_id, till_code)
                cashier_id = get_or_create_cashier(cur, cashier_external_id)

                # создаём чек
                cur.execute(
                    """
                    INSERT INTO prismalite.receipts (
                        store_id,
                        till_id,
                        cashier_id,
                        number,
                        operation_type,
                        business_date,
                        opened_at,
                        closed_at,
                        total_amount
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        store_id,
                        till_id,
                        cashier_id,
                        receipt_number,
                        operation_type,
                        business_date,
                        opened_at,
                        closed_at,
                        total_amount,
                    ),
                )
                receipt_id = cur.fetchone()[0]

                # создаём позиции чека
                for idx, item in enumerate(items, start=1):
                    line_number = item.get("line_number", idx)
                    barcode = item.get("barcode")
                    sku = item.get("sku")
                    name = item.get("name")
                    quantity = item.get("quantity")
                    price = item.get("price")
                    amount = item.get("amount")
                    vat_rate = item.get("vat_rate")

                    cur.execute(
                        """
                        INSERT INTO prismalite.receipt_items (
                            receipt_id,
                            line_number,
                            barcode,
                            sku,
                            name,
                            quantity,
                            price,
                            amount,
                            vat_rate
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            receipt_id,
                            line_number,
                            barcode,
                            sku,
                            name,
                            quantity,
                            price,
                            amount,
                            vat_rate,
                        ),
                    )

                # линкуем события по номеру чека (correlation_id)
                cur.execute(
                    """
                    UPDATE prismalite.events
                    SET receipt_id = %s
                    WHERE store_id = %s
                      AND till_id = %s
                      AND correlation_id = %s
                      AND receipt_id IS NULL
                    """,
                    (receipt_id, store_id, till_id, receipt_number),
                )

        return receipt_id
    finally:
        conn.close()
