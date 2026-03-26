from __future__ import annotations

from typing import Dict, List, Sequence

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
            "Return JSON in the form {\"raw_header\": \"RequiredColumn\"}."
        )
        response = self._client.generate_content(prompt)
        text = response.text or "{}"
        try:
            import json

            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except Exception:  # noqa: BLE001
            logger.warning("Failed to parse Gemini mapping response.")
        return {}
