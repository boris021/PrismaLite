from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.integrations.setretail_client import (
    fetch_new_purchases_raw,
    fetch_purchases_by_period,
)
from app.integrations.setretail_parser import parse_purchases_xml

router = APIRouter(prefix="/setretail", tags=["SetRetail"])


@router.get("/pull-test")
def pull_new_purchases_test():
    """
    Тест: забрать новые чеки из SetRetail за сегодняшний операционный день
    для магазина 50 (все кассы), распарсить и вернуть JSON.
    Может вернуть count=0, если "новых" чеков нет.
    """
    try:
        date_operday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        xml_bytes = fetch_new_purchases_raw(
            date_operday=date_operday,
            shop_number=50,
            cash_number=None,
            shift_number=None,
            purchase_number=None,
            limit=100,
        )

        purchases = parse_purchases_xml(xml_bytes)

        return {
            "oper_day": date_operday.isoformat(),
            "shop": 50,
            "count": len(purchases),
            "purchases": [p.dict() for p in purchases],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pull-period")
def pull_by_period():
    """
    Получаем ВСЕ чеки за период 25.11.2025 00:00–23:59,
    парсим XML и отдаём первые 10 чеков в JSON.
    """
    try:
        date_from = datetime(2025, 11, 25, 0, 0, 0)
        date_to = datetime(2025, 11, 25, 23, 59, 59)

        raw_bytes = fetch_purchases_by_period(
            date_from=date_from,
            date_to=date_to,
        )

        # парсим XML -> список Purchase
        purchases = parse_purchases_xml(raw_bytes)

        # для отладки — берём первые 10 чеков
        preview_purchases = purchases[:10]

        # можно сразу при необходимости фильтровать по магазину 50:
        # preview_purchases = [p for p in purchases if p.shop == "50"][:10]

        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "total_count": len(purchases),
            "preview_count": len(preview_purchases),
            "purchases": [p.dict() for p in preview_purchases],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
