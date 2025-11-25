import base64
import logging
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


def fetch_new_purchases_raw() -> bytes:
    """
    Вызывает SetRetail SOAP: getNewPurchasesByOperDay()
    Возвращает XML байты.
    """
    client = get_client()

    try:
        response = client.service.getNewPurchasesByOperDay()
    except Fault as e:
        logger.error(f"SOAP Fault: {e}")
        raise
    except TransportError as e:
        logger.error(f"Transport error: {e}")
        raise

    if isinstance(response, bytes):
        raw_bytes = response
    else:
        raw_bytes = str(response).encode("utf-8")

    try:
        xml_bytes = base64.b64decode(raw_bytes)
    except Exception:
        xml_bytes = raw_bytes

    return xml_bytes
