from __future__ import annotations

import json
from typing import List, Optional

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

        prompt = (
            "You are an executive analyst. Based on the summary below, write 4 concise executive bullets "
            "explaining the WHY behind the numbers (not just the what). Return JSON as {\"bullets\": [..]}.\n"
            f"KPI Summary: {analysis.kpis}\n"
            f"Top Products: {analysis.top_products}\n"
            f"Outliers: {analysis.outliers}\n"
        )
        text = self.llm_client.generate_text(prompt)
        bullets = self._parse_bullets(text)
        return bullets or self._fallback_bullets(analysis)

    def _parse_bullets(self, text: str) -> List[str]:
        try:
            data = json.loads(text)
            bullets = data.get("bullets", [])
            if isinstance(bullets, list):
                return [str(b).strip() for b in bullets if str(b).strip()]
        except Exception:  # noqa: BLE001
            logger.warning("Failed to parse insight bullets from LLM response.")
        return []

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
