from __future__ import annotations

import json
from typing import List, Optional, Dict

from pydantic import BaseModel, ValidationError, field_validator

from .analysis_engine import AnalysisResult
from .logger import get_logger

logger = get_logger(__name__)


class InsightGenerator:
    def __init__(self, llm_client: Optional[object]) -> None:
        self.llm_client = llm_client

    def generate_sections(
        self,
        analysis: AnalysisResult,
        prompt_override: Optional[str] = None,
        previous_analysis: Optional[dict] = None,
    ) -> Dict[str, List[str]]:
        if not self.llm_client:
            return self._fallback_sections(analysis)

        try:
            prompt = prompt_override or self._default_prompt(analysis, previous_analysis)
            text = self.llm_client.generate_text(prompt)
            sections = self._parse_sections(text)
            if not sections:
                bullets, recommendations = self._salvage_from_text(text)
                sections = self._fallback_sections(analysis, bullets, recommendations)
            return sections
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM insight generation failed; using fallback sections. %s", exc)
            return self._fallback_sections(analysis)

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

    def _parse_sections(self, text: str) -> Dict[str, List[str]]:
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            data = self._extract_json(text)
        if not isinstance(data, dict):
            return {}

        # Accept full section schema
        try:
            model = ReportSectionsSchema.model_validate(data)
            return model.to_sections()
        except ValidationError:
            pass

        # Accept legacy bullets schema
        try:
            model = BulletsSchema.model_validate(data)
            return self._fallback_sections(None, model.bullets, model.recommendations)
        except ValidationError:
            logger.warning("Bullets schema validation failed.")
            return {}

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

    def _fallback_sections(
        self,
        analysis: AnalysisResult | None,
        bullets: Optional[List[str]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        bullets = bullets or self._fallback_bullets(analysis) if analysis else (bullets or [])
        recommendations = recommendations or self._fallback_recommendations(analysis) if analysis else (recommendations or [])
        overview = []
        if analysis:
            overview = [
                f"Rows: {analysis.data_quality.get('rows', '0')} | Columns: {analysis.data_quality.get('columns', '0')}",
                f"Missing %: {analysis.data_quality.get('missing_pct', '0.00%')} | Duplicates: {analysis.data_quality.get('duplicate_rows', '0')}",
            ]
        return {
            "title": ["Executive Summary"],
            "executive_summary": bullets[:5],
            "objectives": ["Clarify performance drivers and highlight risks for decision-making."],
            "data_overview": overview or ["Dataset overview not available."],
            "methodology": ["Aggregated KPIs, top products, and outliers using SQL-based analysis."],
            "key_findings": bullets[:5],
            "insights_interpretation": bullets[:5],
            "department_analysis": ["Department-specific implications derived from KPI performance."],
            "comparative_analysis": ["Comparison requires prior period data; see variance slide when available."],
            "risks_limitations": ["Results depend on data completeness and schema alignment."],
            "recommendations": recommendations[:3],
            "conclusion": ["Performance shows measurable drivers that can be optimized."],
            "next_steps": ["Validate drivers with stakeholders and monitor leading indicators."],
            "appendix": ["Supporting tables and definitions available upon request."],
        }

    def _fallback_bullets(self, analysis: AnalysisResult | None) -> List[str]:
        bullets: List[str] = []
        if analysis and "MoM Growth" in analysis.kpis:
            bullets.append("Month-over-month change suggests recent demand shift worth validating.")
        if analysis and analysis.top_products:
            bullets.append("Top categories are driving revenue concentration; protect supply and margin.")
        if analysis and analysis.outliers:
            bullets.append("Revenue outliers may indicate one-off deals or data quality issues.")
        if not bullets:
            bullets.append("Data indicates stable performance with no major anomalies detected.")
        return bullets[:4]

    def _fallback_recommendations(self, analysis: AnalysisResult | None) -> List[str]:
        recommendations: List[str] = []
        if analysis and analysis.top_products:
            recommendations.append("Protect supply and pricing for top categories to sustain revenue concentration.")
        if analysis and analysis.outliers:
            recommendations.append("Validate outlier records and investigate drivers to separate one-offs from trends.")
        if analysis and "MoM Growth" in analysis.kpis:
            recommendations.append("Align marketing and inventory with the latest demand signal to stabilize momentum.")
        while len(recommendations) < 3:
            recommendations.append("Review KPI drivers weekly and adjust tactics based on leading indicators.")
        return recommendations[:3]

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


class ReportSectionsSchema(BaseModel):
    title: str
    executive_summary: List[str]
    objectives: List[str]
    data_overview: List[str]
    methodology: List[str]
    key_findings: List[str]
    insights_interpretation: List[str]
    department_analysis: List[str]
    comparative_analysis: List[str]
    risks_limitations: List[str]
    recommendations: List[str]
    conclusion: List[str]
    next_steps: List[str]
    appendix: List[str]

    def to_sections(self) -> Dict[str, List[str]]:
        return {
            "title": [self.title],
            "executive_summary": self.executive_summary,
            "objectives": self.objectives,
            "data_overview": self.data_overview,
            "methodology": self.methodology,
            "key_findings": self.key_findings,
            "insights_interpretation": self.insights_interpretation,
            "department_analysis": self.department_analysis,
            "comparative_analysis": self.comparative_analysis,
            "risks_limitations": self.risks_limitations,
            "recommendations": self.recommendations,
            "conclusion": self.conclusion,
            "next_steps": self.next_steps,
            "appendix": self.appendix,
        }
