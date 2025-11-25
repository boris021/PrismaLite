import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

import yaml

from sender import BackendClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("prismalite.agent")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_test_receipt_edr() -> Dict[str, Any]:
    """Тестовый чек, чтобы проверить полный цикл agent → backend → DB."""
    return {
        "store": {"code": "MSK01"},
        "till": {"code": "KASSA-01"},
        "cashier": {"external_id": "1234"},
        "receipt": {
            "number": "R-TEST-001",
            "operation_type": "SALE",
            "business_date": datetime.utcnow().date().isoformat(),
            "total_amount": 123.45,
            "items": [
                {
                    "line_number": 1,
                    "barcode": "4601234567890",
                    "sku": "000000123",
                    "name": "Тестовый товар",
                    "quantity": 1,
                    "price": 123.45,
                    "amount": 123.45,
                    "vat_rate": 12.0,
                }
            ],
        },
    }


def build_test_event_edr() -> Dict[str, Any]:
    """Тестовое событие, связанное с чеком R-TEST-001."""
    return {
        "store": {"code": "MSK01"},
        "till": {"code": "KASSA-01"},
        "cashier": {"external_id": "1234"},
        "event": {
            "code": 20,
            "occurred_at": datetime.utcnow().isoformat(),
        },
        "receipt": {
            "number": "R-TEST-001",
            "operation_type": "SALE",
            "business_date": datetime.utcnow().date().isoformat(),
        },
        "payload": {
            "barcode": "4601234567890",
            "name": "Тестовый товар",
            "quantity": 1,
            "price": 123.45,
            "amount": 123.45,
        },
        "raw": {
            "source": "agent",
            "line": "TEST FROM AGENT",
        },
    }


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
    client = BackendClient(
        base_url=backend_cfg["base_url"],
        events_endpoint=backend_cfg["events_endpoint"],
        receipts_endpoint=backend_cfg["receipts_endpoint"],
    )

    # 1) Шлём тестовый чек
    receipt_edr = build_test_receipt_edr()
    logger.info("Sending test receipt EDR: %s", receipt_edr)
    receipt_resp = client.send_receipt(receipt_edr)
    logger.info("Receipt response: %s", receipt_resp)

    # 2) Шлём тестовое событие, связанное с этим чеком
    event_edr = build_test_event_edr()
    logger.info("Sending test event EDR: %s", event_edr)
    event_resp = client.send_event(event_edr)
    logger.info("Event response: %s", event_resp)


if __name__ == "__main__":
    main()
