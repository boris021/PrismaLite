from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.integrations.setretail_client import fetch_new_purchases_raw

router = APIRouter(prefix="/setretail", tags=["SetRetail"])


@router.get("/pull-test")
def pull_new_purchases_test():
    """
    DEBUG: забираем сырые данные из SetRetail и возвращаем текстом,
    без парсинга XML, чтобы увидеть, что реально приходит.
    """
    try:
        date_operday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        xml_bytes = fetch_new_purchases_raw(
            date_operday=date_operday,
            shop_number=None,
            cash_number=None,
            shift_number=None,
            purchase_number=None,
            limit=100,
        )

        # ѕревращаем байты в строку, даже если там не XML
        raw_text = xml_bytes.decode("utf-8", errors="replace")

        # ¬озвращаем первые, скажем, 2000 символов, чтобы не утонуть
        return {
            "len": len(raw_text),
            "preview": raw_text[:2000],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
