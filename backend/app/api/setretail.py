# backend/app/api/setretail.py
from fastapi import APIRouter, HTTPException

from app.integrations.setretail_client import fetch_new_purchases_raw
from app.integrations.setretail_parser import parse_purchases_xml

router = APIRouter(prefix="/setretail", tags=["SetRetail"])


@router.get("/pull-test")
def pull_new_purchases_test():
    """
    Тестовый endpoint: забирает новые чеки из SetRetail и возвращает их в JSON.
    Потом вместо return будем класть в БД.
    """
    try:
        xml_bytes = fetch_new_purchases_raw()
        purchases = parse_purchases_xml(xml_bytes)
        return {
            "count": len(purchases),
            "purchases": [p.dict() for p in purchases],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
