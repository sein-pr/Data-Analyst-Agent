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

    def generate_bullets(
        self,
        analysis: AnalysisResult,
        prompt_override: Optional[str] = None,
        previous_analysis: Optional[dict] = None,
    ) -> List[str]:
        if not self.llm_client:
            return self._fallback_bullets(analysis)

        try:
            prompt = prompt_override or self._default_prompt(analysis, previous_analysis)
            text = self.llm_client.generate_text(prompt)
            bullets, recommendations = self._parse_bullets(text)
            if not bullets:
                bullets, recommendations = self._salvage_from_text(text)
            bullets = self._validate_bullets(bullets)
            if not recommendations:
                recommendations = self._fallback_recommendations(analysis)
            if recommendations:
                return bullets + [f"Rec: {r}" for r in recommendations]
            return bullets or self._fallback_bullets(analysis)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM insight generation failed; using fallback bullets. %s", exc)
            return self._fallback_bullets(analysis)

    def _default_prompt(self, analysis: AnalysisResult, previous_analysis: Optional[dict]) -> str:
        comparison = ""
        if previous_analysis:
            comparison = f"\n- Previous KPI Summary: {previous_analysis.get('kpis', {})}\n"
        return (
            "You are an executive analyst tasked with analyzing KPI data and identifying causal drivers of performance.\n\n"
            "## Your Task\n"
            "Analyze the provided KPI summary, top products, and outliers to identify root causes and patterns - not "
            "descriptive summaries of what happened. Your analysis should reveal the WHY behind performance movements.\n\n"
            "## Deliverable Requirements\n"
            "Bullets:\n"
            "- Each bullet must be a single sentence, maximum 50 words\n"
            "- Focus exclusively on causal analysis\n"
            "- Avoid restating metrics; instead, explain what's driving the numbers\n\n"
            "Recommendations (exactly 3):\n"
            "- Short, specific, and directly actionable\n\n"
            "## Input Data\n"
            f"- KPI Summary: {analysis.kpis}\n"
            f"- Top Products: {analysis.top_products}\n"
            f"- Outliers: {analysis.outliers}\n"
            f"{comparison}\n"
            "## Output Format (Strict JSON Only)\n"
            "{\"bullets\": [\"bullet 1\", \"bullet 2\", \"bullet 3\"], \"recommendations\": [\"recommendation 1\", \"recommendation 2\", \"recommendation 3\"]}\n\n"
            "Return ONLY valid JSON."
        )

    def _parse_bullets(self, text: str) -> tuple[List[str], List[str]]:
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            data = self._extract_json(text)
        bullets = []
        recommendations = []
        if isinstance(data, dict):
            try:
                model = BulletsSchema.model_validate(data)
                bullets = model.bullets
                recommendations = model.recommendations
            except ValidationError:
                try:
                    model = StructuredSchema.model_validate(data)
                    bullets = [
                        f"{item.headline}: {item.description}".strip(": ").strip()
                        for item in model.insights
                    ]
                    recommendations = [
                        f"{item.action} (Impact: {item.impact})".strip()
                        for item in model.recommendations
                    ]
                except ValidationError:
                    logger.warning("Bullets schema validation failed.")
        if not bullets:
            logger.warning("Failed to parse insight bullets from LLM response.")
        return bullets, recommendations

    def _salvage_from_text(self, text: str) -> tuple[List[str], List[str]]:
        if not text:
            return [], []
        bullets: List[str] = []
        recommendations: List[str] = []
        for line in text.splitlines():
            cleaned = self._sanitize_text(line).lstrip("-*").strip()
            if not cleaned:
                continue
            lower = cleaned.lower()
            if "recommend" in lower:
                continue
            bullets.append(cleaned)
        if not bullets:
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            bullets = sentences[:5]
        if "recommend" in text.lower():
            rec_section = text.lower().split("recommend")[1]
            for line in rec_section.splitlines():
                cleaned = self._sanitize_text(line).lstrip("-*").strip()
                if cleaned:
                    recommendations.append(cleaned)
        return bullets[:5], recommendations[:3]

    def _validate_bullets(self, bullets: List[str]) -> List[str]:
        clean = []
        for bullet in bullets:
            if not bullet or not isinstance(bullet, str):
                continue
            text = self._sanitize_text(bullet).replace("\n", " ").strip()
            words = text.split()
            if len(words) > 50:
                text = " ".join(words[:50]).rstrip() + "..."
            clean.append(text)
        if len(clean) > 5:
            return clean[:5]
        return clean

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

    def _fallback_recommendations(self, analysis: AnalysisResult) -> List[str]:
        recommendations: List[str] = []
        if analysis.top_products:
            recommendations.append("Protect supply and pricing for top categories to sustain revenue concentration.")
        if analysis.outliers:
            recommendations.append("Validate outlier records and investigate drivers to separate one-offs from trends.")
        if "MoM Growth" in analysis.kpis:
            recommendations.append("Align marketing and inventory with the latest demand signal to stabilize momentum.")
        while len(recommendations) < 3:
            recommendations.append("Review KPI drivers weekly and adjust tactics based on leading indicators.")
        return recommendations[:3]

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        replacements = {
            "**": "",
            "__": "",
            "`": "",
            "#": "",
            ">": "",
            "|": " ",
            "\t": " ",
            "\\u2022": "",
        }
        for key, value in replacements.items():
            text = text.replace(key, value)
        text = " ".join(text.split())
        return text


class BulletsSchema(BaseModel):
    bullets: List[str]
    recommendations: List[str] = []

    @field_validator("bullets")
    @classmethod
    def _clean_bullets(cls, value: List[str]) -> List[str]:
        cleaned = [str(b).strip() for b in value if str(b).strip()]
        return cleaned

    @field_validator("recommendations")
    @classmethod
    def _clean_recommendations(cls, value: List[str]) -> List[str]:
        cleaned = [str(b).strip() for b in value if str(b).strip()]
        return cleaned


class InsightItem(BaseModel):
    headline: str
    description: str


class RecommendationItem(BaseModel):
    action: str
    impact: str


class StructuredSchema(BaseModel):
    title: str
    insights: List[InsightItem]
    recommendations: List[RecommendationItem]
