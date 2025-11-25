import base64
import logging
from typing import List

from zeep import Client, Transport
from zeep.exceptions import Fault, TransportError

from app.core.config import settings

logger = logging.getLogger("prismalite.setretail")


def build_wsdl_url() -> str:
    cfg = settings.setretail
    return f"http://{cfg.host}:{cfg.port}{cfg.path}?wsdl"


def get_client() -> Client:
    wsdl_url = build_wsdl_url()
    logger.info(f"Creating SetRetail SOAP client for {wsdl_url}")
    transport = Transport(timeout=settings.setretail.request_timeout_sec)
    client = Client(wsdl=wsdl_url, transport=transport)
    return client


def fetch_new_purchases_raw() -> bytes:
    """
    Вызывает метод getNewPurchasesByOperDay (или аналогичный)
    и возвращает RAW Base64-поток с XML, как его отдаёт SetRetail.
    """
    client = get_client()

    try:
        # ВНИМАНИЕ:
        # Сигнатура метода и параметры зависят от документации SetRetail.
        # Здесь — общий пример. Когда увидим WSDL/метод — поправим.
        #
        # response = client.service.getNewPurchasesByOperDay(shop=..., operDay=...)
        response = client.service.getNewPurchasesByOperDay()

    except Fault as e:
        logger.error(f"SetRetail SOAP Fault: {e}")
        raise
    except TransportError as e:
        logger.error(f"SetRetail transport error: {e}")
        raise

    # Часто SetRetail возвращает XML в Base64-строке, например:
    # <return>UEsDBBQAAAAI...</return>
    if isinstance(response, bytes):
        raw_bytes = response
    else:
        # иногда это str (Base64-строка)
        raw_bytes = str(response).encode("utf-8")

    try:
        xml_bytes = base64.b64decode(raw_bytes)
    except Exception:
        logger.warning("Response is not base64 or decode failed, using raw bytes as XML")
        xml_bytes = raw_bytes

    return xml_bytes
