import requests
import psycopg2
import base64
from datetime import datetime
from xml.etree import ElementTree as ET
import os

# ================================
# Настройки
# ================================

SETRETAIL_HOST = "192.168.50.90"

# SOAP Endpoint из WSDL (без ?wsdl)
ERP_URL = f"http://{SETRETAIL_HOST}:8090/SET-ERPIntegration/FiscalInfoExport"

PG_CONN = "dbname=prismalite user=prismalite password=PrismaLite123! host=127.0.0.1 port=5432"

# Папка, куда будем складывать сырые ответы ERP (для анализа)
RAW_DIR = os.path.join(os.path.dirname(__file__), "_raw_erp")
os.makedirs(RAW_DIR, exist_ok=True)


def build_soap_getNewPurchasesByParams(oper_day: datetime) -> str:
    """
    Строим SOAP-запрос для getNewPurchasesByParams.

    В WSDL тип:
      dateOperDay (xs:dateTime)
      shopNumber (long, minOccurs=0)
      cashNumber (long, minOccurs=0)
      shiftNumber (long, minOccurs=0)
      purchaseNumber (long, minOccurs=0)
      limit (long, minOccurs=0)
    Мы пока отправим только dateOperDay (все остальное пусто).
    """
    date_str = oper_day.isoformat()
    # Простое тело: только дата операционного дня
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


def call_getNewPurchasesByParams():
    """
    Вызывает SOAP метод getNewPurchasesByParams.
    Возвращает распакованные байты из <return> (base64) или None.
    """
    oper_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    soap_body = build_soap_getNewPurchasesByParams(oper_day)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        # soapAction по WSDL пустой, так что можно не указывать или оставить пустым:
        "SOAPAction": ""
    }

    print(f"→ SOAP запрос к ERPIntegration: {ERP_URL}")
    print(f"→ Дата операционного дня: {oper_day.isoformat()}")

    r = requests.post(ERP_URL, data=soap_body.encode("utf-8"), headers=headers, timeout=60)
    print(f"← HTTP статус: {r.status_code}")
    print(f"← Content-Type: {r.headers.get('Content-Type')}")

    # Если не 200 — просто выводим тело и выходим
    if r.status_code != 200:
        print("❌ Статус не 200, тело ответа:")
        print(r.text[:1000])
        return None

    # Парсим SOAP-ответ
    try:
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"❌ Не удалось распарсить XML SOAP: {e}")
        print(r.text[:1000])
        return None

    ns = {
        "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "erp": "http://plugins.operday.ERPIntegration.crystals.ru/"
    }

    # Пытаемся найти элемент <erp:getNewPurchasesByParamsResponse><return>...</return>
    ret_el = root.find(".//erp:getNewPurchasesByParamsResponse/erp:return", ns)
    if ret_el is None or not ret_el.text:
        # Иногда return может быть без префикса, попробуем по-другому
        ret_el = root.find(".//return")
        if ret_el is None or not ret_el.text:
            print("⚠ Не найден элемент <return> с данными (возможно, нет новых чеков или другая структура).")
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

    # Сохраняем в файл для анализа (потом посмотрим, xml это или zip и как выглядит структура)
    fname = os.path.join(RAW_DIR, f"purchases_{oper_day.strftime('%Y%m%d')}.bin")
    with open(fname, "wb") as f:
        f.write(raw_bytes)
    print(f"💾 Сырые данные сохранены в файл: {fname}")

    # Попробуем напечатать начало как текст (на случай, если это XML)
    try:
        preview = raw_bytes[:1000].decode("utf-8", errors="ignore")
        print("——— ПРЕВЬЮ содержимого (как UTF-8) ———")
        print(preview)
        print("————————————")
    except Exception:
        pass

    return raw_bytes


def sync_receipts():
    """
    Временная версия: только ходит в ERPIntegration и сохраняет сырые данные.
    К Postgres пока не лезем, пока не поймём точный формат внутри.
    """
    raw = call_getNewPurchasesByParams()
    if raw is None or len(raw) == 0:
        print("⚠ Данные от ERPIntegration не получены или пустые.")
        return

    print("✅ ERPIntegration отработал, данные получены. Парсинг и запись в БД сделаем следующим шагом.")


if __name__ == "__main__":
    sync_receipts()
