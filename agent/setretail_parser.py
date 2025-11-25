from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class ParsedEvent:
    """
    Результат разбора одной строки лога Set Retail.

    Это ещё не EDR целиком, а нормализованная структура,
    из которой мы потом собираем JSON для /api/v1/ingest.
    """
    store_code: str
    till_code: str
    cashier_external_id: Optional[str]
    event_code: int
    occurred_at: datetime
    receipt_number: Optional[str]
    payload: Dict[str, Any]
    raw_line: str


def parse_setretail_line(
    line: str,
    default_store: str,
    default_till: str,
) -> Optional[ParsedEvent]:
    """
    Черновой парсер строки Set Retail.

    ⚠ ВАЖНО:
    Формат здесь гипотетический, чтобы был каркас.
    Когда будет реальный пример строки лога,
    мы просто поменяем эту функцию.

    Допустим, строка выглядит так (пример):

    2025-11-25 13:20:01;MSK01;KASSA-01;1234;20;R-12345;barcode=4601234567890;qty=1;price=249;amount=249

    Формат:
    0: datetime (YYYY-MM-DD HH:MM:SS)
    1: store_code
    2: till_code
    3: cashier_external_id
    4: event_code (int)
    5: receipt_number
    6+: пара ключ=значение (payload)
    """
    line = line.strip()
    if not line:
        return None

    parts = line.split(";")
    if len(parts) < 5:
        # Мало полей — пропускаем
        return None

    # Время
    ts_str = parts[0]
    try:
        occurred_at = datetime.fromisoformat(ts_str)
    except ValueError:
        # Если формат другой — временно игнорируем строку
        return None

    store_code = parts[1].strip() or default_store
    till_code = parts[2].strip() or default_till
    cashier_external_id = parts[3].strip() or None

    try:
        event_code = int(parts[4])
    except ValueError:
        return None

    receipt_number: Optional[str] = None
    payload: Dict[str, Any] = {}

    # Если есть номер чека
    if len(parts) > 5:
        receipt_number = parts[5].strip() or None

    # Остальное считаем key=value
    for field in parts[6:]:
        field = field.strip()
        if not field or "=" not in field:
            continue
        key, value = field.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Пробуем чуть-чуть привести типы
        if value.replace(".", "", 1).isdigit():
            try:
                if "." in value:
                    payload[key] = float(value)
                else:
                    payload[key] = int(value)
                continue
            except ValueError:
                pass
        payload[key] = value

    return ParsedEvent(
        store_code=store_code or default_store,
        till_code=till_code or default_till,
        cashier_external_id=cashier_external_id,
        event_code=event_code,
        occurred_at=occurred_at,
        receipt_number=receipt_number,
        payload=payload,
        raw_line=line,
    )
