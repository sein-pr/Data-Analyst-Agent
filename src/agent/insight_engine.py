from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .analysis_engine import AnalysisResult
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class Insight:
    title: str
    bullets: List[str]


@dataclass
class VisualizationSuggestion:
    title: str
    chart_type: str
    description: str


class InsightEngine:
    def __init__(self) -> None:
        self.pandasai_available = self._check_pandasai()

    def generate_insights(self, df: pd.DataFrame, analysis: AnalysisResult) -> List[Insight]:
        if not self.pandasai_available:
            return self._fallback_insights(analysis)
        prompt = (
            "Generate up to 5 concise insights. "
            "Return JSON array like "
            "[{\"title\":\"...\",\"bullets\":[\"...\",\"...\"]}]. "
            "Each bullet must be short (max 15-20 words)."
        )
        response = self._pandasai_chat(prompt, df, analysis)
        insights = self._parse_insights(response)
        return insights or self._fallback_insights(analysis)

    def suggest_visualizations(self, df: pd.DataFrame, analysis: AnalysisResult) -> List[VisualizationSuggestion]:
        if not self.pandasai_available:
            return self._fallback_visualizations(analysis)
        prompt = (
            "Suggest up to 3 charts for the key insights. "
            "Return JSON array like "
            "[{\"title\":\"...\",\"chart_type\":\"bar|line|pie|scatter\",\"description\":\"...\"}]."
        )
        response = self._pandasai_chat(prompt, df, analysis)
        suggestions = self._parse_visualizations(response)
        return suggestions or self._fallback_visualizations(analysis)

    def _pandasai_chat(self, prompt: str, df: pd.DataFrame, analysis: AnalysisResult) -> str:
        try:
            import pandasai as pai
        except Exception as exc:  # noqa: BLE001
            logger.warning("PandasAI not available: %s", exc)
            return ""

        kpi_df = pd.DataFrame(
            [{"metric": k, "value": v} for k, v in analysis.kpis.items()]
        )
        top_df = pd.DataFrame(analysis.top_products)
        outlier_df = pd.DataFrame(analysis.outliers)
        overview_df = pd.DataFrame([analysis.data_quality])

        try:
            response = pai.chat(
                prompt,
                df,
                kpi_df,
                top_df,
                outlier_df,
                overview_df,
            )
            return self._response_to_text(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PandasAI chat failed: %s", exc)
            return ""

    @staticmethod
    def _response_to_text(response) -> str:
        if isinstance(response, str):
            return response
        value = getattr(response, "value", None)
        if value is None:
            return str(response)
        return str(value)

    def _parse_insights(self, text: str) -> List[Insight]:
        data = self._extract_json(text)
        insights: List[Insight] = []
        if isinstance(data, list):
            for item in data[:5]:
                title = str(item.get("title", "")).strip()
                bullets = [str(b).strip() for b in item.get("bullets", []) if str(b).strip()]
                if title and bullets:
                    insights.append(Insight(title=title, bullets=bullets[:3]))
        return insights

    def _parse_visualizations(self, text: str) -> List[VisualizationSuggestion]:
        data = self._extract_json(text)
        suggestions: List[VisualizationSuggestion] = []
        if isinstance(data, list):
            for item in data[:3]:
                title = str(item.get("title", "")).strip()
                chart_type = str(item.get("chart_type", "")).strip()
                description = str(item.get("description", "")).strip()
                if title and chart_type:
                    suggestions.append(
                        VisualizationSuggestion(
                            title=title,
                            chart_type=chart_type,
                            description=description,
                        )
                    )
        return suggestions

    @staticmethod
    def _extract_json(text: str):
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:  # noqa: BLE001
                    return None
        return None

    @staticmethod
    def _fallback_insights(analysis: AnalysisResult) -> List[Insight]:
        insights: List[Insight] = []
        if "MoM Growth" in analysis.kpis:
            insights.append(
                Insight(
                    title="Momentum",
                    bullets=["Month-over-month change suggests a recent demand shift worth validating."],
                )
            )
        if analysis.top_products:
            insights.append(
                Insight(
                    title="Revenue Concentration",
                    bullets=["Top categories drive revenue; protect supply and margin in these lines."],
                )
            )
        if analysis.outliers:
            insights.append(
                Insight(
                    title="Outliers",
                    bullets=["Outliers may reflect one-off deals or data quality issues."],
                )
            )
        if not insights:
            insights.append(
                Insight(
                    title="Stability",
                    bullets=["Performance appears stable with no major anomalies detected."],
                )
            )
        return insights[:5]

    @staticmethod
    def _fallback_visualizations(analysis: AnalysisResult) -> List[VisualizationSuggestion]:
        suggestions: List[VisualizationSuggestion] = []
        if analysis.top_products:
            suggestions.append(
                VisualizationSuggestion(
                    title="Top Products by Revenue",
                    chart_type="bar",
                    description="Compare top product categories by total revenue.",
                )
            )
        if analysis.monthly_revenue:
            suggestions.append(
                VisualizationSuggestion(
                    title="Monthly Revenue Trend",
                    chart_type="line",
                    description="Track revenue over time to show momentum.",
                )
            )
        if analysis.outliers:
            suggestions.append(
                VisualizationSuggestion(
                    title="Outlier Revenue",
                    chart_type="bar",
                    description="Highlight unusually high revenue points.",
                )
            )
        return suggestions[:3]

    @staticmethod
    def _check_pandasai() -> bool:
        try:
            import pandasai  # noqa: F401

            return True
        except Exception:
            return False
