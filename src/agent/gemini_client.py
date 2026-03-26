from __future__ import annotations

import json
import re
from typing import Dict, List, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from .logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    def __init__(self, api_keys: List[str], model: str) -> None:
        if not api_keys:
            raise ValueError("At least one Gemini API key is required.")
        self.api_keys = api_keys
        self._key_index = 0
        self.model = model
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("google-generativeai is not installed.") from exc
        genai.configure(api_key=self._current_key())
        self._client = genai.GenerativeModel(self.model)

    def map_columns(self, required_columns: Sequence[str], raw_headers: List[str]) -> Dict[str, str]:
        prompt = (
            "You are a data schema mapper. Map the raw column headers to the required schema.\n"
            f"Required columns: {', '.join(required_columns)}\n"
            f"Raw headers: {', '.join(raw_headers)}\n"
            "Return ONLY strict JSON in the form {\"raw_header\": \"RequiredColumn\"}.\n"
            "Do not include any commentary or markdown."
        )
        text = self._generate_with_key_rotation(prompt)
        return self._parse_json_mapping(text)

    def generate_text(self, prompt: str) -> str:
        return self._generate_with_key_rotation(prompt)

    def _generate_with_key_rotation(self, prompt: str) -> str:
        last_exc = None
        for _ in range(len(self.api_keys)):
            try:
                self._ensure_client()
                response = self._client.generate_content(prompt)
                return response.text or ""
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if self._is_quota_error(exc):
                    logger.warning("Gemini quota/rate error; switching API key.")
                    self._rotate_key()
                    continue
                raise
        if last_exc:
            raise last_exc
        return ""

    def _rotate_key(self) -> None:
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        self._client = None

    def _current_key(self) -> str:
        return self.api_keys[self._key_index]

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        indicators = [
            "quota",
            "rate",
            "exhausted",
            "resource_exhausted",
            "429",
            "too many requests",
            "expired",
            "invalid",
        ]
        return any(token in text for token in indicators)

    def _parse_json_mapping(self, text: str) -> Dict[str, str]:
        parsed = self._extract_json(text)
        if isinstance(parsed, dict):
            try:
                model = MappingSchema.model_validate(parsed)
                if model.mapping:
                    return model.mapping
            except ValidationError:
                logger.warning("Mapping schema validation failed.")
        logger.warning("Failed to parse Gemini mapping response.")
        return {}

    @staticmethod
    def _extract_json(text: str):
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except Exception:  # noqa: BLE001
                return None


class MappingSchema(BaseModel):
    mapping: Dict[str, str] = {}

    @classmethod
    def model_validate(cls, data):  # type: ignore[override]
        if isinstance(data, dict) and "mapping" not in data:
            data = {"mapping": data}
        return super().model_validate(data)

    @field_validator("mapping")
    @classmethod
    def _clean_mapping(cls, value: Dict[str, str]):
        cleaned = {}
        for key, val in value.items():
            if not key or not val:
                continue
            cleaned[str(key)] = str(val)
        return cleaned
