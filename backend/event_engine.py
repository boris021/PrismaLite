import psycopg2
from psycopg2.extras import Json
from datetime import datetime, timedelta

DB = {
    "host": "localhost",
    "dbname": "prismalite",
    "user": "postgres",
    "password": "postgres",  # <-- сюда твой пароль
}

# Порог большой скидки (50%)
BIG_DISCOUNT_RATIO = 0.5


def get_connection():
    conn = psycopg2.connect(**DB)
    # ВКЛЮЧАЕМ AUTOCOMMIT, чтобы не залипать в aborted-транзакции
    conn.autocommit = True
    return conn


def fetch_recent_receipts(cur, hours=24):
    """
    Берём чеки за последние N часов.
    """
    cur.execute(
        """
        SELECT id, shop, cash, shift, number, sale_time, amount, discount_amount, is_refund
        FROM receipts
        WHERE sale_time >= now() - (%s || ' hours')::interval
        ORDER BY sale_time DESC
        """,
        (hours,),
    )
    return cur.fetchall()


def fetch_positions_for_receipt(cur, receipt_id: int):
    cur.execute(
        """
        SELECT id, pos_order, goods_code, bar_code, count, cost, nds, is_void, raw_json
        FROM receipt_positions
        WHERE receipt_id = %s
        ORDER BY pos_order NULLS FIRST, id
        """,
        (receipt_id,),
    )
    return cur.fetchall()


def clear_events_for_receipts(cur, receipt_ids):
    if not receipt_ids:
        return
    cur.execute(
        "DELETE FROM events WHERE receipt_id = ANY(%s)",
        (receipt_ids,),
    )


def create_event(cur, receipt_id, position_id, event_type, severity, details: dict):
    cur.execute(
        """
        INSERT INTO events (receipt_id, position_id, event_type, severity, details)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (receipt_id, position_id, event_type, severity, Json(details)),
    )


def process_receipt(cur, receipt_row, positions):
    """
    Логика правил.
    receipt_row: (id, shop, cash, shift, number, sale_time, amount, discount_amount, is_refund)
    """
    (
        receipt_id,
        shop,
        cash,
        shift,
        number,
        sale_time,
        amount,
        discount_amount,
        is_refund,
    ) = receipt_row

    # 1) Возврат всего чека
    if is_refund or (amount is not None and amount < 0):
        create_event(
            cur,
            receipt_id,
            None,
            "REFUND_RECEIPT",
            "medium",
            {
                "shop": shop,
                "cash": cash,
                "shift": shift,
                "number": number,
                "amount": float(amount) if amount is not None else None,
            },
        )

    # 2) Большая скидка по чеку
    try:
        if discount_amount is not None and amount is not None and amount > 0:
            disc_ratio = float(discount_amount) / float(amount)
            if disc_ratio >= BIG_DISCOUNT_RATIO:
                create_event(
                    cur,
                    receipt_id,
                    None,
                    "BIG_RECEIPT_DISCOUNT",
                    "high",
                    {
                        "shop": shop,
                        "cash": cash,
                        "shift": shift,
                        "number": number,
                        "amount": float(amount),
                        "discount_amount": float(discount_amount),
                        "discount_ratio": disc_ratio,
                    },
                )
    except Exception as e:
        print(f"[WARN] receipt {receipt_id}: discount calc error: {e}")

    # 3) Позиции: VOID, огромная скидка, «ручная цена»
    for pos in positions:
        (
            pos_id,
            pos_order,
            goods_code,
            bar_code,
            cnt,
            cost,
            nds,
            is_void,
            raw_json,
        ) = pos

        # VOID позиция
        if is_void:
            create_event(
                cur,
                receipt_id,
                pos_id,
                "VOID_POSITION",
                "medium",
                {
                    "goods_code": goods_code,
                    "bar_code": bar_code,
                    "pos_order": pos_order,
                    "count": float(cnt) if cnt is not None else None,
                    "cost": float(cost) if cost is not None else None,
                },
            )

        # Большая скидка по позиции
        try:
            if isinstance(raw_json, dict):
                discount = raw_json.get("discount")
                price = raw_json.get("price") or cost
                if discount and price:
                    disc_ratio = float(discount) / float(price)
                    if disc_ratio >= BIG_DISCOUNT_RATIO:
                        create_event(
                            cur,
                            receipt_id,
                            pos_id,
                            "BIG_ITEM_DISCOUNT",
                            "high",
                            {
                                "goods_code": goods_code,
                                "bar_code": bar_code,
                                "pos_order": pos_order,
                                "price": float(price),
                                "discount": float(discount),
                                "discount_ratio": disc_ratio,
                            },
                        )
        except Exception as e:
            print(f"[WARN] receipt {receipt_id}, pos {pos_id}: discount calc error: {e}")

        # Подозрительная «ручная» цена
        try:
            if cost is not None and float(cost) in (1.0, 2.0, 3.0):
                create_event(
                    cur,
                    receipt_id,
                    pos_id,
                    "MANUAL_PRICE_SUSPECT",
                    "medium",
                    {
                        "goods_code": goods_code,
                        "bar_code": bar_code,
                        "pos_order": pos_order,
                        "count": float(cnt) if cnt is not None else None,
                        "cost": float(cost),
                    },
                )
        except Exception as e:
            print(f"[WARN] receipt {receipt_id}, pos {pos_id}: manual price check error: {e}")


def run_event_engine(hours=24):
    conn = get_connection()
    cur = conn.cursor()

    print(f"[INFO] Running EventEngine for last {hours} hours...")
    receipts = fetch_recent_receipts(cur, hours=hours)
    print(f"[INFO] Loaded {len(receipts)} receipts")

    receipt_ids = [r[0] for r in receipts]
    clear_events_for_receipts(cur, receipt_ids)
    print(f"[INFO] Cleared existing events for {len(receipt_ids)} receipts")

    for r in receipts:
        receipt_id = r[0]
        try:
            positions = fetch_positions_for_receipt(cur, receipt_id)
        except Exception as e:
            print(f"[ERROR] fetch positions for receipt {receipt_id}: {e}")
            continue

        try:
            process_receipt(cur, r, positions)
        except Exception as e:
            print(f"[ERROR] process receipt {receipt_id}: {e}")
            # продолжаем дальше, не валим весь движок
            continue

    cur.close()
    conn.close()
    print("[INFO] EventEngine finished")


if __name__ == "__main__":
    run_event_engine(hours=24)
