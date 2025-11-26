from datetime import datetime
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import get_connection


router = APIRouter(tags=["incidents"])


# ============================
#   МОДЕЛИ ДЛЯ API
# ============================

class IncidentStatus(str, Enum):
    new = "new"
    in_progress = "in_progress"
    closed = "closed"
    false_positive = "false_positive"


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    comment: Optional[str] = None
    updated_by: Optional[str] = None


# ============================
#   СПИСОК ИНЦИДЕНТОВ
# ============================

@router.get("/incidents")
def list_incidents(
    severity: Optional[List[str]] = Query(
        default=None,
        description="Фильтр по severity: A/B/C",
    ),
    status: Optional[List[str]] = Query(
        default=None,
        description="Фильтр по статусу: new/in_progress/closed/false_positive",
    ),
    shop: Optional[str] = Query(
        default=None,
        description="Фильтр по магазину (shop)",
    ),
    date_from: Optional[datetime] = Query(
        default=None,
        description="Начало периода по sale_time",
    ),
    date_to: Optional[datetime] = Query(
        default=None,
        description="Конец периода по sale_time (включительно)",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Список инцидентов с фильтрами.

    Возвращает:
      - items: список инцидентов
      - total: общее количество (для пагинации)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        where_clauses = ["1=1"]
        params: List = []

        # severity[]
        if severity:
            where_clauses.append("severity = ANY(%s)")
            params.append(severity)

        # status[]
        if status:
            where_clauses.append("status = ANY(%s)")
            params.append(status)

        # магазин
        if shop:
            where_clauses.append("shop = %s")
            params.append(shop)

        # период по sale_time
        if date_from:
            where_clauses.append("sale_time >= %s")
            params.append(date_from)
        if date_to:
            # включительно
            where_clauses.append("sale_time <= %s")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)

        # total
        cur.execute(
            f"""
            SELECT COUNT(*)
            FROM incidents
            WHERE {where_sql}
            """,
            params,
        )
        total = cur.fetchone()[0]

        # данные
        cur.execute(
            f"""
            SELECT
                id,
                receipt_id,
                severity,
                status,
                shop,
                cash,
                shift,
                number,
                sale_time,
                event_types,
                events_count,
                video_from,
                video_to,
                created_at,
                updated_at
            FROM incidents
            WHERE {where_sql}
            ORDER BY sale_time DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

        incidents = []
        for row in rows:
            (
                id_,
                receipt_id,
                severity_,
                status_,
                shop_,
                cash_,
                shift_,
                number_,
                sale_time_,
                event_types,
                events_count,
                video_from,
                video_to,
                created_at,
                updated_at,
            ) = row

            incidents.append(
                {
                    "id": id_,
                    "receipt_id": receipt_id,
                    "severity": severity_,
                    "status": status_,
                    "shop": shop_,
                    "cash": cash_,
                    "shift": shift_,
                    "number": number_,
                    "sale_time": sale_time_,
                    "event_types": event_types or [],
                    "events_count": events_count,
                    "video_from": video_from,
                    "video_to": video_to,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        return {
            "items": incidents,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


# ============================
#   ДЕТАЛЬНЫЙ ИНЦИДЕНТ + СОБЫТИЯ
# ============================

@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int):
    """
    Детальная карточка инцидента:
      - incident: данные из incidents
      - events: связанные события по incident_events
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # сам инцидент
        cur.execute(
            """
            SELECT
                id,
                receipt_id,
                severity,
                status,
                shop,
                cash,
                shift,
                number,
                sale_time,
                event_types,
                events_count,
                video_from,
                video_to,
                video_meta,
                created_at,
                updated_at,
                last_comment,
                updated_by
            FROM incidents
            WHERE id = %s
            """,
            (incident_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="incident not found")

        (
            id_,
            receipt_id,
            severity_,
            status_,
            shop_,
            cash_,
            shift_,
            number_,
            sale_time_,
            event_types,
            events_count,
            video_from,
            video_to,
            video_meta,
            created_at,
            updated_at,
            last_comment,
            updated_by,
        ) = row

        incident = {
            "id": id_,
            "receipt_id": receipt_id,
            "severity": severity_,
            "status": status_,
            "shop": shop_,
            "cash": cash_,
            "shift": shift_,
            "number": number_,
            "sale_time": sale_time_,
            "event_types": event_types or [],
            "events_count": events_count,
            "video_from": video_from,
            "video_to": video_to,
            "video_meta": video_meta,
            "created_at": created_at,
            "updated_at": updated_at,
            "last_comment": last_comment,
            "updated_by": updated_by,
        }

        # связанные события
        cur.execute(
            """
            SELECT
                e.id,
                e.event_type,
                e.severity,
                e.created_at,
                e.details
            FROM incident_events ie
            JOIN events e ON e.id = ie.event_id
            WHERE ie.incident_id = %s
            ORDER BY e.created_at ASC, e.id ASC
            """,
            (incident_id,),
        )
        events = []
        for (
            ev_id,
            ev_type,
            ev_severity,
            ev_created_at,
            ev_details,
        ) in cur.fetchall():
            events.append(
                {
                    "id": ev_id,
                    "event_type": ev_type,
                    "severity": ev_severity,
                    "created_at": ev_created_at,
                    "details": ev_details,
                }
            )

        return {"incident": incident, "events": events}
    finally:
        conn.close()


# ============================
#   СМЕНА СТАТУСА ИНЦИДЕНТА
# ============================

@router.patch("/incidents/{incident_id}/status")
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
):
    """
    Смена статуса инцидента:
      - status: new / in_progress / closed / false_positive
      - comment: опциональный комментарий
      - updated_by: кто изменил (логин / ФИО)

    Требует столбцы в incidents:
      - status incident_status NOT NULL
      - updated_at timestamptz NOT NULL
      - last_comment text NULL
      - updated_by text NULL
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE incidents
            SET
                status = %s,
                updated_at = NOW(),
                last_comment = COALESCE(%s, last_comment),
                updated_by = COALESCE(%s, updated_by)
            WHERE id = %s
            RETURNING
                id,
                receipt_id,
                severity,
                status,
                shop,
                cash,
                shift,
                number,
                sale_time,
                event_types,
                events_count,
                video_from,
                video_to,
                video_meta,
                created_at,
                updated_at,
                last_comment,
                updated_by
            """,
            (
                payload.status.value,
                payload.comment,
                payload.updated_by,
                incident_id,
            ),
        )

        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="incident not found")

        (
            id_,
            receipt_id,
            severity_,
            status_,
            shop_,
            cash_,
            shift_,
            number_,
            sale_time_,
            event_types,
            events_count,
            video_from,
            video_to,
            video_meta,
            created_at,
            updated_at,
            last_comment,
            updated_by,
        ) = row

        conn.commit()

        return {
            "id": id_,
            "receipt_id": receipt_id,
            "severity": severity_,
            "status": status_,
            "shop": shop_,
            "cash": cash_,
            "shift": shift_,
            "number": number_,
            "sale_time": sale_time_,
            "event_types": event_types or [],
            "events_count": events_count,
            "video_from": video_from,
            "video_to": video_to,
            "video_meta": video_meta,
            "created_at": created_at,
            "updated_at": updated_at,
            "last_comment": last_comment,
            "updated_by": updated_by,
        }
    finally:
        conn.close()
