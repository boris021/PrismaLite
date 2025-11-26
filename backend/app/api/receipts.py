from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException

from app.db.models import insert_receipt_with_items

from app.db.models import insert_receipt_with_items
from app.db.connection import get_connection   # ← ДОБАВИЛИ

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

@router.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: int):
    """
    Детальная карточка чека:
    - данные из receipts
    - позиции из receipt_positions
    - события из events
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. сам чек
            cur.execute(
                """
                SELECT
                    id,
                    shop,
                    cash,
                    shift,
                    number,
                    oper_day,
                    sale_time,
                    amount,
                    discount_amount,
                    is_refund
                FROM receipts
                WHERE id = %s
                """,
                (receipt_id,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Receipt not found")

            (
                r_id,
                shop,
                cash,
                shift,
                number,
                oper_day,
                sale_time,
                amount,
                discount_amount,
                is_refund,
            ) = row

            receipt = {
                "id": r_id,
                "shop": shop,
                "cash": cash,
                "shift": shift,
                "number": number,
                "oper_day": oper_day,
                "sale_time": sale_time,
                "amount": float(amount) if amount is not None else None,
                "discount_amount": float(discount_amount)
                if discount_amount is not None
                else None,
                "is_refund": is_refund,
            }

            # 2. позиции чека
            cur.execute(
                """
                SELECT
                    id,
                    pos_order,
                    goods_code,
                    bar_code,
                    count,
                    cost,
                    nds,
                    is_void,
                    raw_json
                FROM receipt_positions
                WHERE receipt_id = %s
                ORDER BY pos_order NULLS FIRST, id
                """,
                (receipt_id,),
            )
            pos_rows = cur.fetchall()

            positions = []
            for (
                p_id,
                pos_order,
                goods_code,
                bar_code,
                count,
                cost,
                nds,
                is_void,
                raw_json,
            ) in pos_rows:
                positions.append(
                    {
                        "id": p_id,
                        "pos_order": pos_order,
                        "goods_code": goods_code,
                        "bar_code": bar_code,
                        "count": float(count) if count is not None else None,
                        "cost": float(cost) if cost is not None else None,
                        "nds": nds,
                        "is_void": is_void,
                        "raw": raw_json,
                    }
                )

            # 3. события по чеку
            cur.execute(
                """
                SELECT
                    id,
                    position_id,
                    event_type,
                    severity,
                    created_at,
                    details
                FROM events
                WHERE receipt_id = %s
                ORDER BY created_at, id
                """,
                (receipt_id,),
            )
            ev_rows = cur.fetchall()

            events = []
            for (
                e_id,
                position_id,
                event_type,
                severity,
                created_at,
                details,
            ) in ev_rows:
                events.append(
                    {
                        "id": e_id,
                        "position_id": position_id,
                        "event_type": event_type,
                        "severity": severity,
                        "created_at": created_at,
                        "details": details or {},
                    }
                )

        receipt["positions"] = positions
        receipt["events"] = events
        return receipt

    finally:
        conn.close()
