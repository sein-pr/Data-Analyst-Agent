from __future__ import annotations

import json
import re
from typing import Dict, List, Sequence

from pydantic import BaseModel, ValidationError, field_validator

from .logger import get_logger

logger = get_logger(__name__)


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("google-generativeai is not installed.") from exc
        genai.configure(api_key=self.api_key)
        self._client = genai.GenerativeModel(self.model)

    def map_columns(self, required_columns: Sequence[str], raw_headers: List[str]) -> Dict[str, str]:
        self._ensure_client()
        prompt = (
            "You are a data schema mapper. Map the raw column headers to the required schema.\n"
            f"Required columns: {', '.join(required_columns)}\n"
            f"Raw headers: {', '.join(raw_headers)}\n"
            "Return ONLY strict JSON in the form {\"raw_header\": \"RequiredColumn\"}.\n"
            "Do not include any commentary or markdown."
        )
        response = self._client.generate_content(prompt)
        text = response.text or "{}"
        return self._parse_json_mapping(text)

    def generate_text(self, prompt: str) -> str:
        self._ensure_client()
        response = self._client.generate_content(prompt)
        return response.text or ""

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
