from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import requests

from .config import EnvConfig
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class WebhookConfig:
    url: str


class WebhookSender:
    def __init__(self, config: Optional[WebhookConfig]) -> None:
        self.config = config

    @classmethod
    def from_config(cls, env: EnvConfig) -> "WebhookSender":
        if not env.webhook_url:
            logger.warning("Webhook URL not configured; outbound events disabled.")
            return cls(None)
        return cls(WebhookConfig(url=env.webhook_url))

    def send(self, event: str, payload: dict) -> None:
        if not self.config:
            return
        body = {"event": event, "payload": payload}
        try:
            requests.post(self.config.url, json=body, timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send webhook event: %s", exc)
