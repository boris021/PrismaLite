from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .base import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    store_id = Column(Integer, nullable=False)
    pos_id = Column(String(32), nullable=False)
    cashier = Column(String(64), nullable=True)
    event_code = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

