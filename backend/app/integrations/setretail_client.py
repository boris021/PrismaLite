import logging
from datetime import datetime
from typing import Optional

from zeep import Client, Transport
from zeep.exceptions import Fault, TransportError

from app.core.config import settings

logger = logging.getLogger("prismalite.setretail")


def build_wsdl_url() -> str:
    cfg = settings.setretail
    return f"http://{cfg.host}:{cfg.port}{cfg.path}?wsdl"


def get_client() -> Client:
    wsdl_url = build_wsdl_url()
    transport = Transport(timeout=settings.setretail.request_timeout_sec)
    client = Client(wsdl=wsdl_url, transport=transport)
    return client


def fetch_new_purchases_raw(
    date_operday: datetime,
    shop_number: Optional[int] = None,
    cash_number: Optional[int] = None,
    shift_number: Optional[int] = None,
    purchase_number: Optional[int] = None,
    limit: Optional[int] = None,
) -> bytes:
    """
    Вызывает метод getNewPurchasesByParams у SetRetail
    и возвращает XML-чеков (байты).

    Параметры:
      date_operday   — операционный день (datetime)
      shop_number    — номер магазина
      cash_number    — номер кассы (можно None, тогда все кассы)
      shift_number   — номер смены (можно None)
      purchase_number— номер чека (можно None)
      limit          — ограничение по количеству чеков
    """
    client = get_client()

    try:
        response = client.service.getNewPurchasesByParams(
            dateOperDay=date_operday,
            shopNumber=shop_number,
            cashNumber=cash_number,
            shiftNumber=shift_number,
            purchaseNumber=purchase_number,
            limit=limit,
        )
    except Fault as e:
        logger.error(f"SetRetail SOAP Fault: {e}")
        raise
    except TransportError as e:
        logger.error(f"SetRetail transport error: {e}")
        raise

    # SetRetail у тебя уже возвращает ЧИСТЫЙ XML (мы это увидели),
    # поэтому просто приводим к bytes, без base64-декодирования.
    if isinstance(response, bytes):
        return response
    else:
        return str(response).encode("utf-8")

def fetch_purchases_by_period(
    date_from: datetime,
    date_to: datetime,
    shop_number: Optional[int] = None,
) -> bytes:

    client = get_client()

    try:
        response = client.service.getPurchasesByPeriod(
            dateFrom=date_from,
            dateTo=date_to,
            shopNumber=shop_number,
        )
    except Fault as e:
        logger.error(f"SOAP Fault: {e}")
        raise
    except TransportError as e:
        logger.error(f"Transport error: {e}")
        raise

    if isinstance(response, bytes):
        return response
    else:
        return str(response).encode("utf-8")
