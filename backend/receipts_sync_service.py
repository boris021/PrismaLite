import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta

SETRETAIL_URL = "http://SETRETAIL_HOST:8080/api/purchases"
PG_CONN = "postgresql://user:password@localhost:5432/prismalite"

def fetch_purchases():
    """
    Дергаем только новые чеки:
    /getNewPurchasesByParams?dateFrom=...&shop=...
    """
    now = datetime.now()
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)

    payload = {
        "dateFrom": date_from.isoformat(),
        "dateTo": now.isoformat(),
        "shops": [],       # можно оставить пустым
        "withPositions": True,
        "withPayments": True
    }

    r = requests.post(f"{SETRETAIL_URL}/getNewPurchasesByParams", json=payload)
    r.raise_for_status()
    return r.json().get("purchases", [])


def sync_receipts():
    purchases = fetch_purchases()
    print(f"Получено чеков: {len(purchases)}")

    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()

    new_count = 0

    for p in purchases:
        shop = p["shop"]
        cash = p["cash"]
        shift = p["shift"]
        number = p["number"]
        sale_time = p["sale_time"]

        # --- Проверяем наличие ---
        cur.execute("""
            SELECT id FROM receipts
            WHERE shop=%s AND cash=%s AND shift=%s AND number=%s
        """, (shop, cash, shift, number))

        row = cur.fetchone()
        if row:
            continue  # чек уже есть

        # --- Вставляем чек ---
        cur.execute("""
            INSERT INTO receipts (uid_purchase, shop, cash, shift, number,
                                  oper_day, sale_time, tab_number, user_name,
                                  amount, discount_amount, inn, status, raw_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            p.get("uid_purchase"),
            shop, cash, shift, number,
            p["oper_day"],
            p["sale_time"],
            p.get("tab_number"),
            p.get("user_name"),
            p.get("amount"),
            p.get("discount_amount"),
            p.get("inn"),
            p.get("status"),
            p
        ))
        receipt_id = cur.fetchone()[0]

        # --- Вставляем позиции ---
        for pos in p.get("positions", []):
            cur.execute("""
                INSERT INTO receipt_positions
                (receipt_id, pos_order, goods_code, bar_code, count,
                 cost, nds, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                receipt_id,
                pos.get("order"),
                pos.get("goods_code"),
                pos.get("bar_code"),
                pos.get("count"),
                pos.get("cost"),
                pos.get("nds"),
                pos
            ))

        # --- Вставляем оплаты ---
        for pay in p.get("payments", []):
            cur.execute("""
                INSERT INTO receipt_payments
                (receipt_id, payment_type, amount, raw_json)
                VALUES (%s,%s,%s,%s)
            """, (
                receipt_id,
                pay.get("type"),
                pay.get("amount"),
                pay
            ))

        new_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Новых чеков сохранено: {new_count}")
    return new_count


if __name__ == "__main__":
    sync_receipts()
