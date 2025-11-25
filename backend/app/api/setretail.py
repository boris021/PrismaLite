from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.integrations.setretail_client import fetch_new_purchases_raw
from app.integrations.setretail_parser import parse_purchases_xml

router = APIRouter(prefix="/setretail", tags=["SetRetail"])


@router.get("/pull-test")
def pull_new_purchases_test():
    """
    Тест: забрать новые чеки из SetRetail за сегодняшний операционный день
    для магазина 50 (все кассы), распарсить и вернуть JSON.
    """
    try:
        # Операционный день = сегодня, 00:00
        date_operday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        xml_bytes = fetch_new_purchases_raw(
            date_operday=date_operday,
            shop_number=50,      # твой магазин 50
            cash_number=None,    # None = обе кассы (1 и 2)
            shift_number=None,
            purchase_number=None,
            limit=100,           # до 100 чеков
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
    Получаем ВСЕ чеки за период (не только новые).
    """
    try:
        date_from = datetime(2025, 11, 25, 0, 0, 0)
        date_to = datetime(2025, 11, 25, 23, 59, 59)

        raw_bytes = fetch_purchases_by_period(
            date_from=date_from,
            date_to=date_to,
            shop_number=50,
        )

        text = raw_bytes.decode("utf-8", errors="replace")
        return {
            "raw_len": len(raw_bytes),
            "raw_preview": text[:4000],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
