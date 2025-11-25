import logging
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)


class BackendClient:
    def __init__(self, base_url: str, events_endpoint: str, receipts_endpoint: str):
        self.base_url = base_url.rstrip("/")
        self.events_url = self.base_url + events_endpoint
        self.receipts_url = self.base_url + receipts_endpoint

    def send_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(self.events_url, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Sent event, response: %s", data)
        return data

    def send_receipt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(self.receipts_url, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Sent receipt, response: %s", data)
        return data
