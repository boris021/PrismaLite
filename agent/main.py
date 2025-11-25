import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import yaml

from sender import BackendClient
from setretail_parser import parse_setretail_line

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prismalite.agent")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_event_edr_from_parsed(parsed, source: str) -> Dict[str, Any]:
    """
    Собираем EDR JSON для /api/v1/ingest из ParsedEvent.
    """
    edr: Dict[str, Any] = {
        "store": {"code": parsed.store_code},
        "till": {"code": parsed.till_code},
        "cashier": {"external_id": parsed.cashier_external_id},
        "event": {
            "code": parsed.event_code,
            "occurred_at": parsed.occurred_at.isoformat(),
        },
        "receipt": {
            "number": parsed.receipt_number,
            "operation_type": "SALE",  # по умолчанию
            "business_date": parsed.occurred_at.date().isoformat(),
        },
        "payload": parsed.payload,
        "raw": {
            "source": source,
            "line": parsed.raw_line,
        },
    }
    return edr


def process_log_file(log_path: Path, client: BackendClient, agent_cfg: Dict[str, Any]) -> None:
    """
    Простейшая обработка лог-файла:
    - читаем файл построчно
    - парсим строку
    - отправляем событие в backend
    """
    default_store = agent_cfg.get("store_code", "UNKNOWN_STORE")
    default_till = agent_cfg.get("till_code", "UNKNOWN_TILL")
    source = agent_cfg.get("source", "setretail")

    if not log_path.exists():
        logger.error("Log file not found: %s", log_path)
        return

    logger.info("Processing log file: %s", log_path)

    sent = 0
    skipped = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_setretail_line(line, default_store, default_till)
            if not parsed:
                skipped += 1
                continue

            edr = build_event_edr_from_parsed(parsed, source)
            try:
                resp = client.send_event(edr)
                sent += 1
                logger.debug("Event sent, response: %s", resp)
            except Exception as e:
                logger.error("Failed to send event: %s", e)

    logger.info("Log processing finished. Sent=%s, skipped=%s", sent, skipped)


def main() -> None:
    root = Path(__file__).resolve().parent
    config_path = root / "config.yaml"

    if not config_path.exists():
        example = root / "config_example.yaml"
        raise SystemExit(
            f"Config {config_path} not found. "
            f"Copy {example.name} to config.yaml and adjust settings."
        )

    config = load_config(config_path)
    backend_cfg = config["backend"]
    agent_cfg = config.get("agent", {})

    client = BackendClient(
        base_url=backend_cfg["base_url"],
        events_endpoint=backend_cfg["events_endpoint"],
        receipts_endpoint=backend_cfg["receipts_endpoint"],
    )

    # Пока: просто обрабатываем один лог-файл целиком
    log_file_path = agent_cfg.get("log_file_path")
    if not log_file_path:
        raise SystemExit("agent.log_file_path is not set in config.yaml")

    process_log_file(Path(log_file_path), client, agent_cfg)


if __name__ == "__main__":
    main()
