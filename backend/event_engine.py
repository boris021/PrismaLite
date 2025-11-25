# backend/event_engine.py

import os
import datetime as dt
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json

# Используем тот же DSN, что и в других модулях.
# Если он у тебя уже задан в .env / docker-compose — просто подгони переменную.
DB_DSN = os.getenv(
    "DATABASE_URL",
    "dbname=prismalite user=postgres password=postgres host=localhost",
)


class EventEngine:
    def __init__(self, dsn: str = DB_DSN):
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)

    # ===== ПУБЛИЧНЫЙ ВХОД =====

    def run_for_period(self, date_from: dt.datetime, date_to: dt.datetime) -> None:
        """
        Основной вход: пройтись по чекам за период и сгенерировать события.
        Это можно дергать из cron / systemd-таймера.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.*
                FROM receipts r
                WHERE r.sale_time >= %s
                  AND r.sale_time < %s
                ORDER BY r.sale_time
                """,
                (date_from, date_to),
            )
            receipts = cur.fetchall()

            for receipt in receipts:
                self.process_receipt(conn, receipt)

    def run_for_receipt(self, receipt_id: int) -> None:
        """
        Помощник: пересчитать события для одного конкретного чека.
        Удобно для дебага.
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM receipts WHERE id = %s",
                (receipt_id,),
            )
            receipt = cur.fetchone()
            if not receipt:
                return
            self.process_receipt(conn, receipt)

    # ===== ОСНОВНАЯ ЛОГИКА НА ОДИН ЧЕК =====

    def process_receipt(self, conn, receipt: Dict[str, Any]) -> None:
        """
        Обработка одного чека:
        - вытащить позиции
        - прогнать через набор правил
        - записать события в таблицу events (без дублей)
        """
        receipt_id = receipt["id"]

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*
                FROM receipt_positions p
                WHERE p.receipt_id = %s
                ORDER BY p.id
                """,
                (receipt_id,),
            )
            positions = cur.fetchall()

        events: List[Dict[str, Any]] = []

        # --- Правила на чек ---
        events.extend(self._rule_return(receipt))

        # --- Правила на позиции ---
        for pos in positions:
            events.extend(self._rule_void(pos))
            events.extend(self._rule_manual_price(pos))
            events.extend(self._rule_weight_anomaly(pos))
            events.extend(self._rule_no_scan_sale(pos))
            events.extend(self._rule_discount_over_limit(pos))

        # Запись в БД
        self._insert_events(conn, receipt_id, events)

    # ===== ПРАВИЛА (по минимуму, дальше будем расширять) =====

    def _rule_void(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # ⚠️ Подгони под реальные поля из receipt_positions:
        # есть ли у тебя флаг is_void / deleted / void_flag ?
        is_void = bool(pos.get("is_void")) or pos.get("count") == 0

        if is_void:
            events.append({
                "event_type": "VOID",
                "severity": "B",
                "position_id": pos["id"],
                "details": {
                    "rule": "VOID",
                    "reason": "position_marked_void",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                    "cost": pos.get("cost"),
                },
            })
        return events

    def _rule_return(self, receipt: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # В JSON у тебя был operation_type: true/false
        # В БД могли назвать operation_type (boolean) или operation_type_bool и т.п.
        operation_type = receipt.get("operation_type")

        if operation_type is False:
            events.append({
                "event_type": "RETURN",
                "severity": "B",
                "position_id": None,
                "details": {
                    "rule": "RETURN",
                    "amount": receipt.get("amount"),
                    "shop": receipt.get("shop"),
                    "cash": receipt.get("cash"),
                    "shift": receipt.get("shift"),
                    "number": receipt.get("number"),
                },
            })
        return events

    def _rule_manual_price(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # insert_type = 2 -> ручной ввод цены
        if pos.get("insert_type") == 2:
            events.append({
                "event_type": "MANUAL_PRICE",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "MANUAL_PRICE",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                    "price": pos.get("cost"),
                },
            })
        return events

    def _rule_weight_anomaly(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # Подстрой под свои поля: is_weight, weight, cost, amount и т.д.
        if not pos.get("is_weight", False):
            return events

        weight = float(pos.get("weight") or 0)
        unit_price = float(pos.get("cost") or 0)
        line_amount = float(pos.get("amount") or 0)
        calc_amount = weight * unit_price
        tolerance = 5.0  # TODO: вынести в настройки

        if weight == 0 or abs(calc_amount - line_amount) > tolerance:
            events.append({
                "event_type": "WEIGHT_ANOMALY",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "WEIGHT_ANOMALY",
                    "weight": weight,
                    "unit_price": unit_price,
                    "line_amount": line_amount,
                    "calc_amount": calc_amount,
                    "tolerance": tolerance,
                },
            })
        return events

    def _rule_no_scan_sale(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        # Нужен флаг "manual_entry" / "input_mode".
        manual_entry = bool(pos.get("manual_entry"))

        if manual_entry:
            events.append({
                "event_type": "NO_SCAN_SALE",
                "severity": "B",
                "position_id": pos["id"],
                "details": {
                    "rule": "NO_SCAN_SALE",
                    "goods_code": pos.get("goods_code"),
                    "bar_code": pos.get("bar_code"),
                },
            })
        return events

    def _rule_discount_over_limit(self, pos: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []

        discount_percent = float(pos.get("discount_percent") or 0)
        discount_amount = float(pos.get("discount_amount") or 0)

        # TODO: потом вынесем в таблицу настроек / rules
        limit_percent = 20.0
        limit_amount = 1000.0

        if discount_percent > limit_percent or discount_amount > limit_amount:
            events.append({
                "event_type": "DISCOUNT_OVER_LIMIT",
                "severity": "A",
                "position_id": pos["id"],
                "details": {
                    "rule": "DISCOUNT_OVER_LIMIT",
                    "discount_percent": discount_percent,
                    "limit_percent": limit_percent,
                    "discount_amount": discount_amount,
                    "limit_amount": limit_amount,
                },
            })
        return events

    # ===== ЗАПИСЬ В БД =====

    def _insert_events(
        self,
        conn,
        receipt_id: int,
        events: List[Dict[str, Any]],
    ) -> None:
        if not events:
            return

        with conn.cursor() as cur:
            for ev in events:
                pos_id: Optional[int] = ev["position_id"]

                # Простейшая защита от дублей:
                cur.execute(
                    """
                    SELECT 1
                    FROM events
                    WHERE receipt_id = %s
                      AND COALESCE(position_id, -1) = COALESCE(%s, -1)
                      AND event_type = %s
                      AND details = %s::jsonb
                    """,
                    (receipt_id, pos_id, ev["event_type"], Json(ev["details"])),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO events (receipt_id, position_id, event_type, severity, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        receipt_id,
                        pos_id,
                        ev["event_type"],
                        ev["severity"],
                        Json(ev["details"]),
                    ),
                )

        conn.commit()


if __name__ == "__main__":
    # Пример: обработать последние 60 минут
    engine = EventEngine()

    now = dt.datetime.now(dt.timezone.utc)
    date_to = now
    date_from = now - dt.timedelta(minutes=60)

    engine.run_for_period(date_from, date_to)
