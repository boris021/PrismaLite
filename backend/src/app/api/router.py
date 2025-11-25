from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_session
from ..db import models
from .schemas import EventPayload

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(payload: EventPayload, session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    event = models.Event(
        tenant_id=payload.tenant_id,
        store_id=payload.store_id,
        pos_id=payload.pos_id,
        cashier=payload.cashier,
        event_code=payload.event_code,
        timestamp=payload.timestamp,
        payload=payload.payload,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return {"event_id": event.id}


@router.get("/latest")
async def list_latest_events(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict]]:
    stmt = select(models.Event).order_by(models.Event.id.desc()).limit(limit)
    result = await session.execute(stmt)
    items = [
        {
            "event_id": row.Event.id,
            "event_code": row.Event.event_code,
            "timestamp": row.Event.timestamp.isoformat(),
        }
        for row in result.all()
    ]
    return {"items": items}


api_router = APIRouter()
api_router.include_router(router)

