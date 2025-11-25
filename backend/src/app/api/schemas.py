from datetime import datetime

from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    tenant_id: int = Field(..., ge=1)
    store_id: int = Field(..., ge=1)
    pos_id: str
    cashier: str | None = None
    event_code: int
    timestamp: datetime
    payload: dict = Field(default_factory=dict)

