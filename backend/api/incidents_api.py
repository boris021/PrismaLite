from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query

from app.db.connection import get_connection

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    severity: Optional[List[str]] = Query(
        None,
        description="Фильтр по severity (A/B/C). Можно несколько: ?severity=A&severity=B",
    ),
    status: Optional[List[str]] = Query(
        None,
        description="Фильтр по статусу (new/in_progress/...). Можно несколько",
    ),
    shop: Optional[str] = Query(
        None,
        description="Фильтр по магазину (поле incidents.shop)",
    ),
    date_from: Optional[datetime] = Query(
        None,
        description="Отбор по sale_time >= date_from",
    ),
    date_to: Optional[datetime] = Query(
        None,
        description="Отбор по sale_time <= date_to",
    ),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Список инцидентов для службы безопасности.
    Возвращает краткую информацию без вложенных событий.
    """
    conn = get_connection()
    try:
        where_clauses = []
        params: List[Any] = []

        if severity:
            where_clauses.append("severity = ANY(%s)")
            params.append(severity)

        if status:
            where_clauses.append("status = ANY(%s)")
            params.append(status)

        if shop:
            where_clauses.append("shop = %s")
            params.append(shop)

        if date_from:
            where_clauses.append("sale_time >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("sale_time <= %s")
            params.append(date_to)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = f"""
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
                created_at,
                updated_at
            FROM incidents
            {where_sql}
            ORDER BY sale_time DESC, id DESC
            LIMIT %s OFFSET %s
        """

        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        incidents: List[Dict[str, Any]] = []
        for (
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
            created_at,
            updated_at,
        ) in rows:
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
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        return incidents
    finally:
        conn.close()


@router.get("/{incident_id}")
def get_incident(incident_id: int):
    """
    Детальная карточка инцидента:
    - сам инцидент
    - все связанные события (через incident_events)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. инцидент
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
                    created_at,
                    updated_at
                FROM incidents
                WHERE id = %s
                """,
                (incident_id,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Incident not found")

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
                created_at,
                updated_at,
            ) = row

            incident: Dict[str, Any] = {
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
                "created_at": created_at,
                "updated_at": updated_at,
            }

            # 2. события по инциденту
            cur.execute(
                """
                SELECT
                    e.id,
                    e.position_id,
                    e.event_type,
                    e.severity,
                    e.created_at,
                    e.details
                FROM incident_events ie
                JOIN events e ON e.id = ie.event_id
                WHERE ie.incident_id = %s
                ORDER BY e.created_at, e.id
                """,
                (incident_id,),
            )
            events_rows = cur.fetchall()

        events: List[Dict[str, Any]] = []
        for (
            e_id,
            position_id,
            event_type,
            severity_e,
            created_at_e,
            details,
        ) in events_rows:
            events.append(
                {
                    "id": e_id,
                    "position_id": position_id,
                    "event_type": event_type,
                    "severity": severity_e,
                    "created_at": created_at_e,
                    "details": details or {},
                }
            )

        incident["events"] = events
        return incident
    finally:
        conn.close()
