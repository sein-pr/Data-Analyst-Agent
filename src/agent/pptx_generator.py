from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from .analysis_engine import AnalysisResult
from .brand import BrandGuidelines
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class SlideContent:
    title: str
    bullets: List[str]


class PPTXGenerator:
    def __init__(self, brand: BrandGuidelines) -> None:
        self.brand = brand

    def build(self, analysis: AnalysisResult, output_path: Path) -> Path:
        prs = Presentation()
        self._add_title_slide(prs, analysis)
        self._add_kpi_slide(prs, analysis)
        self._add_self_healing_slide(prs, analysis)
        self._add_recommendations_slide(prs, analysis)
        self._apply_theme(prs)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        logger.info("Saved presentation to %s", output_path)
        return output_path

    def _apply_theme(self, prs: Presentation) -> None:
        # Minimal theme application, using brand palette for title styling.
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.name = "Calibri"
                        run.font.color.rgb = RGBColor.from_string(self.brand.palette.primary[1:])

    def _add_title_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = f"{self.brand.name} Executive Summary"
        subtitle.text = self.brand.tagline or "Automated Insights"

    def _add_kpi_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        title = slide.shapes.title
        title.text = "KPI Dashboard"
        left = Inches(0.8)
        top = Inches(1.6)
        width = Inches(8.5)
        height = Inches(3.5)
        tx_box = slide.shapes.add_textbox(left, top, width, height)
        tf = tx_box.text_frame
        for key, value in analysis.kpis.items():
            p = tf.add_paragraph()
            p.text = f"{key}: {value}"
            p.font.size = Pt(20)

    def _add_self_healing_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Self-Healing Report"
        left = Inches(0.8)
        top = Inches(1.6)
        width = Inches(8.5)
        height = Inches(3.5)
        tx_box = slide.shapes.add_textbox(left, top, width, height)
        tf = tx_box.text_frame
        tf.text = "New or unexpected columns were detected and normalized."

    def _add_recommendations_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Recommendations"
        left = Inches(0.8)
        top = Inches(1.6)
        width = Inches(8.5)
        height = Inches(3.5)
        tx_box = slide.shapes.add_textbox(left, top, width, height)
        tf = tx_box.text_frame
        tf.text = "Review top-performing categories and investigate outliers."
