import os
from datetime import datetime
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# Загружаем .env из текущего каталога
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "prismalite")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "21945"))
AGENT_SOURCE = os.getenv("AGENT_SOURCE", "setretail10")

app = Flask(__name__)


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def parse_dt(dt_str: str):
    """
    SetPrisma формат: '15.01.2024 16:30:00.000'
    """
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S.%f")
    except ValueError:
        # На всякий случай без миллисекунд
        try:
            return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S")
        except ValueError:
            return None


def store_event(conn, event: dict):
    """
    Сохраняем один элемент из массива events[] в pos_events.
    Структура event описана в разделе 4.3 SetPrisma v3.0.:contentReference[oaicite:4]{index=4}
    """
    prefix = event.get("prefix")
    shop = event.get("shop")
    device = event.get("device")
    code = event.get("code")
    dt = parse_dt(event.get("dateTime"))

    shift_number = event.get("shiftNumber")
    tab_number = event.get("tabNumber")
    employee = event.get("employee")

    document = event.get("document") or {}
    document_number = document.get("number")
    document_type = document.get("type")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pos_events (
                source, prefix, shop, device, code,
                event_datetime, shift_number, tab_number, employee,
                document_number, document_type, payload
            )
            VALUES (%s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s)
            """,
            (
                AGENT_SOURCE,
                prefix,
                shop,
                device,
                code,
                dt,
                shift_number,
                tab_number,
                employee,
                document_number,
                document_type,
                Json(event),
            ),
        )


def store_document(conn, doc: dict):
    """
    Сохраняем итоговый документ (полный чек) в pos_documents.:contentReference[oaicite:5]{index=5}
    Структура в разделе 4.4/6.6.
    """
    prefix = doc.get("prefix")
    shop = doc.get("shop")
    shop_name = doc.get("shopName")
    device = doc.get("device")
    device_name = doc.get("deviceName")
    shift_number = doc.get("shiftNumber")
    tab_number = doc.get("tabNumber")
    employee = doc.get("employee")

    doc_type = doc.get("type")
    doc_number = doc.get("number")
    amount = doc.get("amount")
    status = doc.get("status")
    dt = parse_dt(doc.get("dateTime"))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pos_documents (
                source, prefix, shop, shop_name, device, device_name,
                shift_number, tab_number, employee,
                doc_type, doc_number, amount, status,
                doc_datetime, raw
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s
            )
            """,
            (
                AGENT_SOURCE,
                prefix,
                shop,
                shop_name,
                device,
                device_name,
                shift_number,
                tab_number,
                employee,
                doc_type,
                doc_number,
                amount,
                status,
                dt,
                Json(doc),
            ),
        )


@app.route("/events", methods=["POST"])
def receive_events():
    """
    Эндпоинт SetPrisma v3: POST /events
    Поддерживает:
      - {"version": "3.0", "events": [ ... ]}
      - {"version": "3.0", "document": { ... }}
    См. раздел 4.1–4.4 и пример сервера из 7.3.:contentReference[oaicite:6]{index=6}
    """
    try:
        data = request.get_json(force=True, silent=False)
        if not data:
            return jsonify({"errorCode": -2, "error": "Empty JSON"}), 200

        processed = 0
        conn = get_connection()
        try:
            if "events" in data and isinstance(data["events"], list):
                for ev in data["events"]:
                    store_event(conn, ev)
                    processed += 1

            if "document" in data and isinstance(data["document"], dict):
                store_document(conn, data["document"])
                processed += 1

            conn.commit()
        finally:
            conn.close()

        return jsonify({"processed": processed}), 200

    except Exception as e:
        # По протоколу SetPrisma ошибка парсинга = errorCode -2.:contentReference[oaicite:7]{index=7}
        return jsonify({"errorCode": -2, "error": str(e)}), 200


if __name__ == "__main__":
    print(f"[AGENT] Starting SetPrisma v3 server on {AGENT_HOST}:{AGENT_PORT}")
    app.run(host=AGENT_HOST, port=AGENT_PORT)
