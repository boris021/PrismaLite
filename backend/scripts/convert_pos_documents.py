import psycopg2
from psycopg2.extras import Json
from datetime import datetime

DB = {
    "host": "localhost",
    "dbname": "prismalite",
    "user": "postgres",
    "password": "postgres",
}


def parse_dt(dt_str):
    if not dt_str:
        return None
    for fmt in ("%d.%m.%Y %H:%M:%S.%f", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    return None


def get_table_columns(cur, table_name: str) -> set:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s;
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


def insert_receipt(cur, receipt_cols, raw_doc):
    shop = raw_doc.get("shop")
    device = raw_doc.get("device")
    number = raw_doc.get("number")
    amount = raw_doc.get("amount")
    dtype = raw_doc.get("type")
    employee = raw_doc.get("employee")
    shift = raw_doc.get("shiftNumber")
    dt = parse_dt(raw_doc.get("dateTime"))

    # oper_day: берём из raw_doc["operDay"], если есть, иначе дата из sale_time
    oper_day = raw_doc.get("operDay")
    if not oper_day and dt is not None:
        oper_day = dt.date()  # тип date, Postgres сам приведёт

    cols = []
    vals = []

    if "shop" in receipt_cols:
        cols.append("shop")
        vals.append(shop)
    if "cash" in receipt_cols:
        cols.append("cash")
        vals.append(device)
    if "device" in receipt_cols:
        cols.append("device")
        vals.append(device)
    if "shift" in receipt_cols:
        cols.append("shift")
        vals.append(shift)
    if "shift_number" in receipt_cols:
        cols.append("shift_number")
        vals.append(shift)
    if "number" in receipt_cols:
        cols.append("number")
        vals.append(number)
    if "sale_time" in receipt_cols:
        cols.append("sale_time")
        vals.append(dt)
    if "amount" in receipt_cols:
        cols.append("amount")
        vals.append(amount)
    if "doc_type" in receipt_cols:
        cols.append("doc_type")
        vals.append(dtype)
    if "employee" in receipt_cols:
        cols.append("employee")
        vals.append(employee)
    if "status" in receipt_cols and "status" in raw_doc:
        cols.append("status")
        vals.append(raw_doc.get("status"))
    if "oper_day" in receipt_cols:
        cols.append("oper_day")
        vals.append(oper_day)

    # json-колонка raw_json
    for json_col in ("raw", "raw_json", "json_data", "payload"):
        if json_col in receipt_cols:
            cols.append(json_col)
            vals.append(Json(raw_doc))
            break

    if not cols:
        raise RuntimeError("Не удалось подобрать ни одной колонки для INSERT в receipts")

    cols_sql = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(vals))

    cur.execute(
        f"""
        INSERT INTO receipts ({cols_sql})
        VALUES ({placeholders})
        RETURNING id;
        """,
        vals,
    )
    return cur.fetchone()[0]


def insert_positions(cur, positions_cols, receipt_id, items):
    """
    Вставка в receipt_positions с авто-подбором колонок.
    """
    for idx, item in enumerate(items):
        cols = ["receipt_id"]
        vals = [receipt_id]

        # Позиционный индекс
        for col_name in ("pos_index", "position_index", "line_number"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(idx)
                break

        # Код товара
        if "goods_code" in positions_cols:
            cols.append("goods_code")
            vals.append(item.get("code") or item.get("item"))
        if "item" in positions_cols:
            cols.append("item")
            vals.append(item.get("item") or item.get("code"))

        # ШК
        for col_name in ("barcode", "bar_code"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(item.get("barcode"))
                break

        # Наименование
        for col_name in ("name", "goods_name"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(item.get("name"))
                break

        # Кол-во
        for col_name in ("count", "quantity", "qty"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(item.get("count") or item.get("quantity"))
                break

        # Цена
        for col_name in ("price", "cost", "unit_price"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(item.get("price"))
                break

        # Сумма
        for col_name in ("amount", "line_amount", "total"):
            if col_name in positions_cols:
                cols.append(col_name)
                vals.append(item.get("amount") or (
                    (item.get("count") or item.get("quantity") or 0)
                    * (item.get("price") or 0)
                ))
                break

        # Скидка
        if "discount" in positions_cols and "discount" in item:
            cols.append("discount")
            vals.append(item.get("discount"))

        # Сырая json-позиция (если есть колонка)
        for json_col in ("raw", "raw_json", "json_data", "payload"):
            if json_col in positions_cols:
                cols.append(json_col)
                vals.append(Json(item))
                break

        cols_sql = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(vals))

        cur.execute(
            f"""
            INSERT INTO receipt_positions ({cols_sql})
            VALUES ({placeholders});
            """,
            vals,
        )


def insert_payments(cur, payments_cols, receipt_id, raw_doc):
    """
    Вставка в receipt_payments (если структура таблицы позволяет).
    Если таблица совсем другая — просто пропускаем, это не критично для событий.
    """
    try:
        amount = raw_doc.get("amount")
        payments = raw_doc.get("payments", [])

        if not payments and not payments_cols:
            # вообще нет таблицы или структура непонятна — просто выходим
            return

        if not payments:
            # создаем одну "авто" оплату
            payments = [
                {
                    "type": "AUTO",
                    "amount": amount,
                }
            ]

        for pay in payments:
            cols = ["receipt_id"]
            vals = [receipt_id]

            if "type" in payments_cols:
                cols.append("type")
                vals.append(pay.get("type"))

            for col_name in ("payment_type", "pay_type"):
                if col_name in payments_cols:
                    cols.append(col_name)
                    vals.append(pay.get("type"))
                    break

            if "amount" in payments_cols:
                cols.append("amount")
                vals.append(pay.get("amount", amount))

            for col_name in ("code", "payment_code"):
                if col_name in payments_cols and "code" in pay:
                    cols.append(col_name)
                    vals.append(pay.get("code"))
                    break

            # сырое json, если есть колонка
            for json_col in ("raw", "raw_json", "json_data", "payload"):
                if json_col in payments_cols:
                    cols.append(json_col)
                    vals.append(Json(pay))
                    break

            cols_sql = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(vals))

            cur.execute(
                f"""
                INSERT INTO receipt_payments ({cols_sql})
                VALUES ({placeholders});
                """,
                vals,
            )
    except Exception as e:
        # Не роняем конвертер из-за странной структуры платежей
        print(f"[WARN] payments skipped: {e}")


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # Узнаём реальные колонки таблиц
    receipts_cols = get_table_columns(cur, "receipts")
    positions_cols = get_table_columns(cur, "receipt_positions")
    payments_cols = get_table_columns(cur, "receipt_payments")

    print("[INFO] receipts columns:", receipts_cols)
    print("[INFO] receipt_positions columns:", positions_cols)
    print("[INFO] receipt_payments columns:", payments_cols)

    # Берём ещё не импортированные документы
    cur.execute(
        """
        SELECT id, raw
        FROM pos_documents
        WHERE imported = false
        ORDER BY id
        LIMIT 1000;
        """
    )
    docs = cur.fetchall()
    print(f"[INFO] Found {len(docs)} documents to import")

    for doc_id, raw_doc in docs:
        try:
            # 1. Чек
            receipt_id = insert_receipt(cur, receipts_cols, raw_doc)

            # 2. Позиции
            items = raw_doc.get("items") or raw_doc.get("goods") or []
            insert_positions(cur, positions_cols, receipt_id, items)

            # 3. Оплаты
            insert_payments(cur, payments_cols, receipt_id, raw_doc)

            # 4. Помечаем документ как импортированный
            cur.execute(
                "UPDATE pos_documents SET imported = true WHERE id = %s",
                (doc_id,),
            )
            conn.commit()
            print(f"[OK] Imported document id={doc_id} → receipt {receipt_id}")

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] document {doc_id}: {e}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
