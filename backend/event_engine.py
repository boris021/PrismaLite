import psycopg2
from psycopg2.extras import Json
from datetime import datetime


# ⚙️ Подключение к БД
# ВАЖНО: Скопируй сюда тот же пароль, который у тебя стоит в scripts/convert_pos_documents.py
DB = {
    "host": "localhost",
    "dbname": "prismalite",
    "user": "postgres",
    "password": "postgres",  # ← ЗАМЕНИ на свой рабочий пароль
}

# Порог «большой скидки» (50% и больше)
BIG_DISCOUNT_RATIO = 0.5

# Маппинг под ENUM event_severity (A/B/C)
# См. в БД: SELECT * FROM pg_type WHERE typname = 'event_severity';
SEVERITY_HIGH = "A"    # критичное
SEVERITY_MEDIUM = "B"  # среднее
SEVERITY_LOW = "C"     # информационное


def get_connection():
    """
    Открываем соединение с автокоммитом,
    чтобы не залипать в aborted-транзакциях.
    """
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    return conn


def fetch_recent_receipts(cur, hours=24):
    """
    Берём чеки за последние N часов.
    Под твою схему: receipts(id, shop, cash, shift, number, sale_time, amount, discount_amount, is_refund)
    """
    cur.execute(
        """
        SELECT id,
               shop,
               cash,
               shift,
               number,
               sale_time,
               amount,
               discount_amount,
               is_refund
        FROM receipts
        WHERE sale_time >= now() - (%s || ' hours')::interval
        ORDER BY sale_time DESC;
        """,
        (hours,),
    )
    return cur.fetchall()


def fetch_positions_for_receipt(cur, receipt_id: int):
    """
    Позиции по чеку из receipt_positions.
    Твоя схема: id, receipt_id, pos_order, goods_code, bar_code, count, cost, nds, is_void, raw_json
    """
    cur.execute(
        """
        SELECT id,
               pos_order,
               goods_code,
               bar_code,
               count,
               cost,
               nds,
               is_void,
               raw_json
        FROM receipt_positions
        WHERE receipt_id = %s
        ORDER BY pos_order NULLS FIRST, id;
        """,
        (receipt_id,),
    )
    return cur.fetchall()


def clear_events_for_receipts(cur, receipt_ids):
    """
    Чистим старые события по этим чекам, чтобы не плодить дубли.
    """
    if not receipt_ids:
        return
    cur.execute(
        "DELETE FROM events WHERE receipt_id = ANY(%s);",
        (receipt_ids,),
    )


def create_event(cur, receipt_id, position_id, event_type, severity, details: dict):
    """
    Вставка события в таблицу events.
    Схема: events(id, receipt_id, position_id, event_type, severity, created_at, details)
    severity — ENUM event_severity (A/B/C).
    """
    cur.execute(
        """
        INSERT INTO events (receipt_id, position_id, event_type, severity, details)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (receipt_id, position_id, event_type, severity, Json(details)),
    )


def process_receipt(cur, receipt_row, positions):
    """
    Основная логика правил по одному чеку.

    receipt_row:
      (id, shop, cash, shift, number, sale_time, amount, discount_amount, is_refund)

    positions:
      список строк из receipt_positions
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

    # ---------- Правило 1. Возврат всего чека ----------
    if is_refund or (amount is not None and amount < 0):
        create_event(
            cur,
            receipt_id,
            None,
            "REFUND_RECEIPT",
            SEVERITY_MEDIUM,
            {
                "shop": shop,
                "cash": cash,
                "shift": shift,
                "number": number,
                "amount": float(amount) if amount is not None else None,
            },
        )

    # ---------- Правило 2. Большая скидка по чеку ----------
    try:
        if discount_amount is not None and amount is not None and amount > 0:
            disc_ratio = float(discount_amount) / float(amount)
            if disc_ratio >= BIG_DISCOUNT_RATIO:
                create_event(
                    cur,
                    receipt_id,
                    None,
                    "BIG_RECEIPT_DISCOUNT",
                    SEVERITY_HIGH,
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

    # ---------- Правила по позициям ----------
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

        # 3.1. VOID позиция
        if is_void:
            create_event(
                cur,
                receipt_id,
                pos_id,
                "VOID_POSITION",
                SEVERITY_MEDIUM,
                {
                    "goods_code": goods_code,
                    "bar_code": bar_code,
                    "pos_order": pos_order,
                    "count": float(cnt) if cnt is not None else None,
                    "cost": float(cost) if cost is not None else None,
                },
            )

        # 3.2. Большая скидка по позиции (discount >= 50% от price)
        try:
            if isinstance(raw_json, dict):
                discount = raw_json.get("discount")
                price = raw_json.get("price") or cost
                if discount is not None and price:
                    disc_ratio = float(discount) / float(price)
                    if disc_ratio >= BIG_DISCOUNT_RATIO:
                        create_event(
                            cur,
                            receipt_id,
                            pos_id,
                            "BIG_ITEM_DISCOUNT",
                            SEVERITY_HIGH,
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

        # 3.3. «Ручная цена» — условно подозрительная, если cost ∈ {1,2,3}
        try:
            if cost is not None and float(cost) in (1.0, 2.0, 3.0):
                create_event(
                    cur,
                    receipt_id,
                    pos_id,
                    "MANUAL_PRICE_SUSPECT",
                    SEVERITY_MEDIUM,
                    {
                        "goods_code": goods_code,
                        "bar_code": bar_code,
                        "pos_order": pos_order,
                        "count": float(cnt) if cnt is not None else None,
                        "cost": float(cost),
                    },
                )
        except Exception as e:
            print(
                f"[WARN] receipt {receipt_id}, pos {pos_id}: manual price check error: {e}"
            )


def run_event_engine(hours=24):
    """
    Основной запуск EventEngine:
    - забираем чеки за последние N часов
    - чистим старые события по этим чекам
    - генерируем новые события по правилам
    """
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
            continue

    cur.close()
    conn.close()
    print("[INFO] EventEngine finished")


if __name__ == "__main__":
    # Можно менять окно анализа (в часах), если надо
    run_event_engine(hours=24)
