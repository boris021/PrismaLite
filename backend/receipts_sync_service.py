import requests
import psycopg2
import base64
import json
from datetime import datetime
from xml.etree import ElementTree as ET
import os

# ================================
# Настройки
# ================================

SETRETAIL_HOST = "192.168.50.90"

# SOAP Endpoint из WSDL (без ?wsdl)
ERP_URL = f"http://{SETRETAIL_HOST}:8090/SET-ERPIntegration/FiscalInfoExport"

# Подключение к PostgreSQL
PG_CONN = "dbname=prismalite user=prismalite password=PrismaLite123! host=127.0.0.1 port=5432"

# Папка для сырых файлов (на всякий случай)
RAW_DIR = os.path.join(os.path.dirname(__file__), "_raw_erp")
os.makedirs(RAW_DIR, exist_ok=True)


# ================================
# SOAP-вызов getNewPurchasesByParams
# ================================

def build_soap_getNewPurchasesByParams(oper_day: datetime) -> str:
    """
    SOAP-обёртка для getNewPurchasesByParams.
    Используем только dateOperDay — нам достаточно.
    """
    date_str = oper_day.isoformat()
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:erp="http://plugins.operday.ERPIntegration.crystals.ru/">
   <soapenv:Header/>
   <soapenv:Body>
      <erp:getNewPurchasesByParams>
         <dateOperDay>{date_str}</dateOperDay>
      </erp:getNewPurchasesByParams>
   </soapenv:Body>
</soapenv:Envelope>
"""
    return body


def call_getNewPurchasesByParams() -> str | None:
    """
    Вызывает SOAP метод getNewPurchasesByParams.
    Возвращает XML-строку <purchases>...</purchases> или None.
    """
    oper_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    soap_body = build_soap_getNewPurchasesByParams(oper_day)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": ""
    }

    print(f"→ SOAP запрос к ERPIntegration: {ERP_URL}")
    print(f"→ Дата операционного дня: {oper_day.isoformat()}")

    r = requests.post(ERP_URL, data=soap_body.encode("utf-8"), headers=headers, timeout=60)
    print(f"← HTTP статус: {r.status_code}")
    print(f"← Content-Type: {r.headers.get('Content-Type')}")

    if r.status_code != 200:
        print("❌ Статус не 200, тело ответа:")
        print(r.text[:1000])
        return None

    # Разбираем SOAP-обертку
    try:
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"❌ Не удалось распарсить SOAP XML: {e}")
        print(r.text[:1000])
        return None

    ns = {
        "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "erp": "http://plugins.operday.ERPIntegration.crystals.ru/"
    }

    ret_el = root.find(".//erp:getNewPurchasesByParamsResponse/erp:return", ns)
    if ret_el is None or not (ret_el.text and ret_el.text.strip()):
        # fallback — ищем любой <return>
        ret_el = root.find(".//return")
        if ret_el is None or not (ret_el.text and ret_el.text.strip()):
            print("⚠ Не найден элемент <return> с данными (возможно, нет новых чеков).")
            print(r.text[:1000])
            return None

    b64_data = ret_el.text.strip()
    print(f"← Длина base64-строки: {len(b64_data)} символов")

    try:
        raw_bytes = base64.b64decode(b64_data)
    except Exception as e:
        print(f"❌ Ошибка base64.decode: {e}")
        return None

    print(f"← Получено сырых байт: {len(raw_bytes)}")

    # Сохраняем сырой файл для отладки
    fname = os.path.join(RAW_DIR, f"purchases_{oper_day.strftime('%Y%m%d_%H%M%S')}.bin")
    try:
        with open(fname, "wb") as f:
            f.write(raw_bytes)
        print(f"💾 Сырые данные сохранены в файл: {fname}")
    except Exception as e:
        print(f"⚠ Не удалось сохранить сырой файл: {e}")

    # Пробуем интерпретировать как UTF-8 XML
    try:
        xml_text = raw_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"❌ Не удалось декодировать bytes → UTF-8: {e}")
        return None

    # Небольшое превью
    print("——— ПРЕВЬЮ XML (начало) ———")
    print(xml_text[:500])
    print("————————————")

    return xml_text


# ================================
# Парсинг XML и запись в PostgreSQL
# ================================

def parse_oper_day(oper_day_str: str | None) -> str | None:
    """
    operDay приходит как '2025-11-25+05:00'
    В БД в DATE достаточно '2025-11-25'.
    """
    if not oper_day_str:
        return None
    # отрежем по '+'
    return oper_day_str.split('+', 1)[0]


def sync_receipts():
    """
    Главная функция:
    1) Получаем XML из getNewPurchasesByParams
    2) Парсим <purchase>
    3) Пишем в PostgreSQL (с дедупликацией)
    """
    xml_text = call_getNewPurchasesByParams()
    if not xml_text:
        print("⚠ XML с чеками не получен (нет новых чеков или ошибка).")
        return

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"❌ Не удалось распарсить XML с чеками: {e}")
        print(xml_text[:1000])
        return

    if root.tag != "purchases":
        print(f"⚠ Ожидался корневой тег <purchases>, а получили <{root.tag}>")
        return

    purchase_elements = root.findall("purchase")
    print(f"→ Найдено покупок в XML: {len(purchase_elements)}")

    if not purchase_elements:
        print("⚠ В XML нет покупок (count=0).")
        return

    conn = psycopg2.connect(PG_CONN)
    cur = conn.cursor()

    new_count = 0

    for purch_el in purchase_elements:
        attrs = purch_el.attrib

        tab_number = attrs.get("tabNumber")
        user_name = attrs.get("userName")
        operation_type_str = attrs.get("operationType")  # "true"/"false"
        is_refund = (operation_type_str == "false" or operation_type_str == "0")
        cash_operation = attrs.get("cashOperation")
        oper_day_str = attrs.get("operDay")
        oper_day = parse_oper_day(oper_day_str)

        shop = attrs.get("shop")
        cash = attrs.get("cash")
        shift = attrs.get("shift")
        number = attrs.get("number")

        sale_time = attrs.get("saletime")  # TIMESTAMP строкой
        amount = attrs.get("amount")
        discount_amount = attrs.get("discountAmount")
        inn = attrs.get("inn")
        fiscal_doc_num = attrs.get("fiscalDocNum")
        status = attrs.get("status")  # может отсутствовать

        # plugin-property для чека
        plugin_props = {}
        uid_purchase = None
        for pp in purch_el.findall("plugin-property"):
            key = pp.get("key")
            value = pp.get("value")
            plugin_props[key] = value
            if key == "UID_PURCHASE":
                uid_purchase = value

        # Дедупликация
        receipt_id = None

        if uid_purchase:
            cur.execute("SELECT id FROM receipts WHERE uid_purchase = %s", (uid_purchase,))
            row = cur.fetchone()
            if row:
                # чек уже есть
                continue

        # если uid_purchase нет или не нашли — проверяем по (shop, cash, shift, number)
        if not uid_purchase:
            cur.execute("""
                SELECT id FROM receipts
                WHERE shop = %s AND cash = %s AND shift = %s AND number = %s
            """, (shop, cash, shift, number))
            row = cur.fetchone()
            if row:
                continue

        # Собираем raw_json для чека
        raw_receipt = {
            "attrs": attrs,
            "plugin_properties": plugin_props
        }

        # INSERT в receipts
        cur.execute("""
            INSERT INTO receipts (
                uid_purchase,
                shop, cash, shift, number,
                oper_day, sale_time,
                tab_number, user_name,
                amount, discount_amount,
                inn, status, is_refund,
                raw_json
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            uid_purchase,
            shop, cash, shift, number,
            oper_day,
            sale_time,
            tab_number, user_name,
            amount, discount_amount,
            inn, status, is_refund,
            json.dumps(raw_receipt, ensure_ascii=False)
        ))

        receipt_id = cur.fetchone()[0]

        # --- Позиции чека ---
        positions_container = purch_el.find("positions")
        if positions_container is not None:
            for pos_el in positions_container.findall("position"):
                pattrs = pos_el.attrib
                pos_order = pattrs.get("order")
                goods_code = pattrs.get("goodsCode")
                bar_code = pattrs.get("barCode")
                count = pattrs.get("count")
                cost = pattrs.get("cost")
                nds = pattrs.get("nds")
                # is_void пока не встречается — считаем False
                is_void = False

                # plugin-property по позиции
                pos_pp = {}
                for ppp in pos_el.findall("plugin-property"):
                    key = ppp.get("key")
                    value = ppp.get("value")
                    pos_pp[key] = value

                raw_pos = {
                    "attrs": pattrs,
                    "plugin_properties": pos_pp
                }

                cur.execute("""
                    INSERT INTO receipt_positions (
                        receipt_id,
                        pos_order,
                        goods_code,
                        bar_code,
                        count,
                        cost,
                        nds,
                        is_void,
                        raw_json
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    receipt_id,
                    pos_order,
                    goods_code,
                    bar_code,
                    count,
                    cost,
                    nds,
                    is_void,
                    json.dumps(raw_pos, ensure_ascii=False)
                ))

        # --- Оплаты ---
        payments_container = purch_el.find("payments")
        if payments_container is not None:
            for pay_el in payments_container.findall("payment"):
                pay_attrs = pay_el.attrib
                payment_type = pay_attrs.get("typeClass")  # BankCardPaymentEntity и т.д.
                pay_amount = pay_attrs.get("amount")

                pay_pp = {}
                for ppp in pay_el.findall("plugin-property"):
                    key = ppp.get("key")
                    value = ppp.get("value")
                    pay_pp[key] = value

                raw_pay = {
                    "attrs": pay_attrs,
                    "plugin_properties": pay_pp
                }

                cur.execute("""
                    INSERT INTO receipt_payments (
                        receipt_id,
                        payment_type,
                        amount,
                        raw_json
                    )
                    VALUES (%s,%s,%s,%s)
                """, (
                    receipt_id,
                    payment_type,
                    pay_amount,
                    json.dumps(raw_pay, ensure_ascii=False)
                ))

        new_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Новых чеков сохранено: {new_count}")


if __name__ == "__main__":
    sync_receipts()
