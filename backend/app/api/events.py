from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from app.db.models import insert_event

router = APIRouter(tags=["events"])


@router.post("/ingest")
async def ingest_events(payload: Dict[str, Any]):
    """
    Принимает либо одно событие EDR, либо batch:
    - одиночное: { ...EDR... }
    - batch: { "events": [ { ...EDR... }, ... ] }
    """
    # Batch-режим: { "events": [ ... ] }
    if "events" in payload and isinstance(payload["events"], list):
        events = payload["events"]
        inserted_ids: List[int] = []
        errors: List[Dict[str, Any]] = []

        for idx, edr in enumerate(events):
            try:
                event_id = insert_event(edr)
                inserted_ids.append(event_id)
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

    # Одиночный EDR-объект
    try:
        event_id = insert_event(payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ingest error: {e}")

    return {"status": "ok", "inserted": 1, "id": event_id}
