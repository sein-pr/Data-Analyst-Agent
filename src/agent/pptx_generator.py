from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
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
        self.logo_full_path = Path("srs/logo_large.png")
        self.logo_symbol_path = Path("srs/logo_small.png")

    def build(self, analysis: AnalysisResult, output_path: Path, bullets: List[str]) -> Path:
        prs = Presentation()
        self._add_title_slide(prs, analysis)
        self._add_kpi_slide(prs, analysis)
        self._add_self_healing_slide(prs, analysis)
        self._add_recommendations_slide(prs, analysis, bullets)
        self._apply_theme(prs)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(output_path)
        logger.info("Saved presentation to %s", output_path)
        return output_path

    def _apply_theme(self, prs: Presentation) -> None:
        for slide in prs.slides:
            self._set_slide_background(slide)
            self._add_footer_logo(slide)
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.name = "Calibri"
                        try:
                            if run.font.color.rgb is None:
                                run.font.color.rgb = RGBColor.from_string(
                                    self.brand.palette.primary[1:]
                                )
                        except Exception:  # noqa: BLE001
                            run.font.color.rgb = RGBColor.from_string(
                                self.brand.palette.primary[1:]
                            )

    def _set_slide_background(self, slide) -> None:
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor.from_string(self.brand.palette.neutral[1:])

    def _add_footer_logo(self, slide) -> None:
        if not self.logo_symbol_path.exists():
            return
        slide.shapes.add_picture(
            str(self.logo_symbol_path),
            Inches(9.0),
            Inches(6.8),
            width=Inches(0.7),
        )

    def _add_header_bar(self, slide) -> None:
        shape = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0),
            Inches(0),
            Inches(13.33),
            Inches(0.35),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(self.brand.palette.primary[1:])
        shape.line.fill.background()

    def _add_title_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_header_bar(slide)

        if self.logo_full_path.exists():
            slide.shapes.add_picture(
                str(self.logo_full_path),
                Inches(0.6),
                Inches(0.7),
                width=Inches(4.0),
            )

        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(2.2), Inches(11.5), Inches(1.0))
        title_tf = title_box.text_frame
        title_tf.text = f"{self.brand.name} Executive Summary"
        title_tf.paragraphs[0].font.size = Pt(42)
        title_tf.paragraphs[0].font.bold = True

        subtitle_box = slide.shapes.add_textbox(Inches(0.6), Inches(3.2), Inches(10.5), Inches(0.8))
        subtitle_tf = subtitle_box.text_frame
        subtitle_tf.text = self.brand.tagline or "Automated Insights"
        subtitle_tf.paragraphs[0].font.size = Pt(22)
        subtitle_tf.paragraphs[0].font.color.rgb = RGBColor.from_string(self.brand.palette.secondary[1:])

    def _add_kpi_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_header_bar(slide)

        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(8.0), Inches(0.6))
        title_tf = title_box.text_frame
        title_tf.text = "KPI Dashboard"
        title_tf.paragraphs[0].font.size = Pt(28)
        title_tf.paragraphs[0].font.bold = True

        kpi_table = slide.shapes.add_table(
            rows=max(2, len(analysis.kpis) + 1),
            cols=2,
            left=Inches(0.6),
            top=Inches(1.6),
            width=Inches(6.2),
            height=Inches(3.6),
        ).table
        kpi_table.cell(0, 0).text = "KPI"
        kpi_table.cell(0, 1).text = "Value"
        self._style_table_header(kpi_table)
        row = 1
        for key, value in analysis.kpis.items():
            kpi_table.cell(row, 0).text = key
            kpi_table.cell(row, 1).text = value
            row += 1

        if analysis.top_products:
            top_table = slide.shapes.add_table(
                rows=len(analysis.top_products) + 1,
                cols=2,
                left=Inches(7.2),
                top=Inches(1.6),
                width=Inches(5.6),
                height=Inches(3.6),
            ).table
            top_table.cell(0, 0).text = "Top Products"
            top_table.cell(0, 1).text = "Revenue"
            self._style_table_header(top_table)
            for idx, item in enumerate(analysis.top_products, start=1):
                top_table.cell(idx, 0).text = item.get("Product Category", "")
                top_table.cell(idx, 1).text = item.get("Revenue", "")

    def _add_self_healing_slide(self, prs: Presentation, analysis: AnalysisResult) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_header_bar(slide)

        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(10.0), Inches(0.6))
        title_tf = title_box.text_frame
        title_tf.text = "Self-Healing Report"
        title_tf.paragraphs[0].font.size = Pt(28)
        title_tf.paragraphs[0].font.bold = True

        body_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12.0), Inches(4.5))
        body_tf = body_box.text_frame
        body_tf.text = "New or unexpected columns were detected and normalized."
        body_tf.paragraphs[0].font.size = Pt(20)

    def _add_recommendations_slide(
        self, prs: Presentation, analysis: AnalysisResult, bullets: List[str]
    ) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_header_bar(slide)

        title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(10.0), Inches(0.6))
        title_tf = title_box.text_frame
        title_tf.text = "Recommendations"
        title_tf.paragraphs[0].font.size = Pt(28)
        title_tf.paragraphs[0].font.bold = True

        left = Inches(0.9)
        top = Inches(1.6)
        width = Inches(11.5)
        height = Inches(4.5)
        tx_box = slide.shapes.add_textbox(left, top, width, height)
        tf = tx_box.text_frame
        tf.word_wrap = True
        if not bullets:
            bullets = ["Review top-performing categories and investigate outliers."]
        tf.text = bullets[0]
        tf.paragraphs[0].font.size = Pt(22)
        tf.paragraphs[0].alignment = PP_ALIGN.LEFT
        for bullet in bullets[1:]:
            p = tf.add_paragraph()
            p.text = bullet
            p.level = 0
            p.font.size = Pt(22)

    def _style_table_header(self, table) -> None:
        for col_idx in range(len(table.columns)):
            cell = table.cell(0, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(self.brand.palette.primary[1:])
            if cell.text_frame.paragraphs:
                for run in cell.text_frame.paragraphs[0].runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.bold = True
