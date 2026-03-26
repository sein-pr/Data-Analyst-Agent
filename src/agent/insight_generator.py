from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, ValidationError, field_validator

from .analysis_engine import AnalysisResult
from .gemini_client import GeminiClient
from .logger import get_logger

logger = get_logger(__name__)


class InsightGenerator:
    def __init__(self, llm_client: Optional[GeminiClient]) -> None:
        self.llm_client = llm_client

    def generate_bullets(self, analysis: AnalysisResult) -> List[str]:
        if not self.llm_client:
            return self._fallback_bullets(analysis)

        try:
            prompt = (
                "You are an executive analyst. Based on the summary below, write 4 concise executive bullets "
                "explaining the WHY behind the numbers (not just the what). "
                "Return ONLY strict JSON as {\"bullets\": [\"...\"]} with exactly 4 items.\n"
                f"KPI Summary: {analysis.kpis}\n"
                f"Top Products: {analysis.top_products}\n"
                f"Outliers: {analysis.outliers}\n"
            )
            text = self.llm_client.generate_text(prompt)
            bullets = self._parse_bullets(text)
            bullets = self._validate_bullets(bullets)
            return bullets or self._fallback_bullets(analysis)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM insight generation failed; using fallback bullets. %s", exc)
            return self._fallback_bullets(analysis)

    def _parse_bullets(self, text: str) -> List[str]:
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            data = self._extract_json(text)
        bullets = []
        if isinstance(data, dict):
            try:
                model = BulletsSchema.model_validate(data)
                bullets = model.bullets
            except ValidationError:
                logger.warning("Bullets schema validation failed.")
        if not bullets:
            logger.warning("Failed to parse insight bullets from LLM response.")
        return bullets

    def _validate_bullets(self, bullets: List[str]) -> List[str]:
        clean = [b.strip() for b in bullets if b and isinstance(b, str)]
        if len(clean) >= 4:
            return clean[:4]
        return clean


class BulletsSchema(BaseModel):
    bullets: List[str]

    @field_validator("bullets")
    @classmethod
    def _clean_bullets(cls, value: List[str]) -> List[str]:
        cleaned = [str(b).strip() for b in value if str(b).strip()]
        return cleaned

    @staticmethod
    def _extract_json(text: str):
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return None

    def _fallback_bullets(self, analysis: AnalysisResult) -> List[str]:
        bullets: List[str] = []
        if "MoM Growth" in analysis.kpis:
            bullets.append("Month-over-month change suggests recent demand shift worth validating.")
        if analysis.top_products:
            bullets.append("Top categories are driving revenue concentration; protect supply and margin.")
        if analysis.outliers:
            bullets.append("Revenue outliers may indicate one-off deals or data quality issues.")
        if not bullets:
            bullets.append("Data indicates stable performance with no major anomalies detected.")
        return bullets[:4]
