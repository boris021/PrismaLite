from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException

from app.db.models import insert_receipt_with_items

router = APIRouter(tags=["receipts"])


@router.post("/receipts/ingest")
async def ingest_receipts(payload: Dict[str, Any]):
    """
    Принимает:
    - один чек: { ...структура чека... }
    - или batch: { "receipts": [ { ... }, { ... } ] }
    """

    # batch-режим
    if "receipts" in payload and isinstance(payload["receipts"], list):
        receipts = payload["receipts"]
        inserted_ids: List[int] = []
        errors: List[Dict[str, Any]] = []

        for idx, rec in enumerate(receipts):
            try:
                receipt_id = insert_receipt_with_items(rec)
                inserted_ids.append(receipt_id)
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        status = "ok" if not errors else "partial"
        return {
            "status": status,
            "inserted": len(inserted_ids),
            "failed": len(errors),
            "ids": inserted_ids,
            "errors": errors,
        }

    # одиночный чек
    try:
        receipt_id = insert_receipt_with_items(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ingest receipt error: {e}")

    return {"status": "ok", "inserted": 1, "id": receipt_id}
