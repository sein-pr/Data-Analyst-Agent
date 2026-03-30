from __future__ import annotations

import json
from typing import Dict, List

import requests

from .logger import get_logger

logger = get_logger(__name__)


class GroqClient:
    def __init__(self, api_keys: List[str], model: str) -> None:
        if not api_keys:
            raise ValueError("At least one Groq API key is required.")
        self.api_keys = api_keys
        self._key_index = 0
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate_text(self, prompt: str) -> str:
        return self._request_with_rotation(prompt)

    def map_columns(self, required_columns: List[str], raw_headers: List[str]) -> Dict[str, str]:
        prompt = (
            "You are a data schema mapper. Map the raw column headers to the required schema.\n"
            f"Required columns: {', '.join(required_columns)}\n"
            f"Raw headers: {', '.join(raw_headers)}\n"
            "Return ONLY strict JSON in the form {\"raw_header\": \"RequiredColumn\"}.\n"
            "Do not include any commentary or markdown."
        )
        text = self._request_with_rotation(prompt)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:  # noqa: BLE001
            return {}
        return {}

    def _request_with_rotation(self, prompt: str) -> str:
        last_exc = None
        for _ in range(len(self.api_keys)):
            try:
                response = requests.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self._current_key()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                    },
                    timeout=30,
                )
                if response.status_code >= 400:
                    raise RuntimeError(response.text)
                payload = response.json()
                return payload["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if self._is_quota_error(exc):
                    logger.warning("Groq quota/rate error; switching API key.")
                    self._rotate_key()
                    continue
                raise
        if last_exc:
            raise last_exc
        return ""

    def _rotate_key(self) -> None:
        self._key_index = (self._key_index + 1) % len(self.api_keys)

    def _current_key(self) -> str:
        return self.api_keys[self._key_index]

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        indicators = ["quota", "rate", "exhausted", "429", "too many requests"]
        return any(token in text for token in indicators)
