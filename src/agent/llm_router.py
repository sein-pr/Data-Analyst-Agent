from __future__ import annotations

from typing import List

from .logger import get_logger

logger = get_logger(__name__)


class LLMRouter:
    def __init__(self, clients: List[object]) -> None:
        self.clients = clients

    def map_columns(self, required_columns, raw_headers):
        last_exc = None
        for client in self.clients:
            try:
                return client.map_columns(required_columns, raw_headers)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("LLM mapping client failed; trying next. %s", exc)
        if last_exc:
            raise last_exc
        return {}

    def generate_text(self, prompt: str) -> str:
        last_exc = None
        for client in self.clients:
            try:
                return client.generate_text(prompt)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("LLM text client failed; trying next. %s", exc)
        if last_exc:
            raise last_exc
        return ""
