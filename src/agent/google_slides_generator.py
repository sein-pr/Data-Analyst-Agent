from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from .analysis_engine import AnalysisResult
from .brand import BrandGuidelines
from .drive_client import DriveService
from .logger import get_logger
from .report_layout_planner import plan_report_layout

logger = get_logger(__name__)

EMU_PER_INCH = 914400


class GoogleSlidesGenerator:
    def __init__(
        self,
        drive: DriveService,
        brand: BrandGuidelines,
        llm_client=None,
    ) -> None:
        self.drive = drive
        self.brand = brand
        self.llm_client = llm_client

    def build(
        self,
        *,
        analysis: AnalysisResult,
        sections: Dict[str, List[str]],
        report_source: str,
        department: str,
        output_folder_id: str,
        selected_kpis: List[str],
        selected_visuals: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        title = f"{self.brand.name} {department.title()} Report - {Path(report_source).stem}"
        created = self.drive.create_presentation(title)
        presentation_id = created["id"]
        self.drive.move_file(presentation_id, output_folder_id)

        existing = self.drive.get_presentation(presentation_id)
        delete_requests = [
            {"deleteObject": {"objectId": s.get("objectId")}}
            for s in existing.get("slides", [])
            if s.get("objectId")
        ]
        if delete_requests:
            self.drive.slides_batch_update(presentation_id, delete_requests)

        plan = plan_report_layout(
            sections=sections,
            kpis=analysis.kpis,
            selected_kpis=selected_kpis,
            selected_visuals=selected_visuals,
            top_products=analysis.top_products,
            outliers=analysis.outliers,
            revenue_by_channel=analysis.revenue_by_channel,
            revenue_by_region=analysis.revenue_by_region,
            department=department,
            llm_client=self.llm_client,
        )
        requests = self._build_requests(
            plan=plan,
            analysis=analysis,
            report_source=report_source,
            department=department,
        )
        if requests:
            self.drive.slides_batch_update(presentation_id, requests)

        return {
            "presentation_id": presentation_id,
            "title": title,
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit",
            "slide_count": len(plan),
        }

    def _build_requests(
        self,
        *,
        plan: List[Dict[str, Any]],
        analysis: AnalysisResult,
        report_source: str,
        department: str,
    ) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        date_text = _utc_today()
        for idx, spec in enumerate(plan, start=1):
            slide_id = _obj_id(f"slide_{idx}")
            requests.append(
                {
                    "createSlide": {
                        "objectId": slide_id,
                        "slideLayoutReference": {"predefinedLayout": "BLANK"},
                    }
                }
            )
            requests.extend(self._add_slide_background(slide_id))
            title = str(spec.get("title") or "Untitled")
            requests.extend(
                self._add_textbox(
                    slide_id,
                    text=title,
                    x=0.5,
                    y=0.35,
                    w=9.0,
                    h=0.6,
                    font_size=26,
                    bold=True,
                    color=self.brand.palette.primary,
                )
            )
            kind = str(spec.get("kind", "bullets")).strip().lower()
            if kind == "title":
                subtitle = [f"{self.brand.name} - {department.title()} Analysis"]
                subtitle.extend((spec.get("bullets") or [])[:2])
                requests.extend(
                    self._add_textbox(
                        slide_id,
                        text="\n".join(subtitle),
                        x=0.7,
                        y=1.4,
                        w=8.6,
                        h=3.8,
                        font_size=20,
                        bold=False,
                        color="#0F172A",
                    )
                )
            elif kind == "bullets":
                bullets = [str(b) for b in (spec.get("bullets") or []) if str(b).strip()]
                if not bullets:
                    bullets = ["Not applicable."]
                bullet_text = "\n".join(f"- {self._wrap(b, 90)}" for b in bullets[:10])
                requests.extend(
                    self._add_textbox(
                        slide_id,
                        text=bullet_text,
                        x=0.7,
                        y=1.2,
                        w=8.8,
                        h=4.9,
                        font_size=17,
                        bold=False,
                        color="#0F172A",
                    )
                )
            elif kind == "kpi_cards":
                requests.extend(self._add_kpi_cards(slide_id, spec.get("kpi_items") or []))
            elif kind == "table":
                requests.extend(self._add_table_slide(slide_id, spec.get("table") or {}))
            elif kind == "chart":
                visual = spec.get("visual") or {}
                requests.extend(self._add_chart_slide(slide_id, visual))
            else:
                fallback = [f"- {self._wrap(v, 90)}" for v in (spec.get("bullets") or [])[:8]]
                requests.extend(
                    self._add_textbox(
                        slide_id,
                        text="\n".join(fallback) if fallback else "- Not applicable.",
                        x=0.7,
                        y=1.4,
                        w=8.8,
                        h=4.8,
                        font_size=17,
                        bold=False,
                        color="#0F172A",
                    )
                )

            requests.extend(
                self._add_textbox(
                    slide_id,
                    text=f"{date_text} | Source: {Path(report_source).name}",
                    x=0.5,
                    y=6.95,
                    w=9.0,
                    h=0.3,
                    font_size=10,
                    bold=False,
                    color=self.brand.palette.primary,
                )
            )
        return requests

    def _add_slide_background(self, slide_id: str) -> List[Dict[str, Any]]:
        shape_id = _obj_id("bg")
        return [
            {
                "createShape": {
                    "objectId": shape_id,
                    "shapeType": "RECTANGLE",
                    "elementProperties": _element_props(slide_id, 0, 0, 10, 7.5),
                }
            },
            {
                "updateShapeProperties": {
                    "objectId": shape_id,
                    "shapeProperties": {
                        "shapeBackgroundFill": {
                            "solidFill": {"color": {"rgbColor": _rgb(self.brand.palette.neutral)}}
                        },
                        "outline": {"propertyState": "NOT_RENDERED"},
                    },
                    "fields": "shapeBackgroundFill.solidFill.color.rgbColor,outline.propertyState",
                }
            },
        ]

    def _add_kpi_cards(self, slide_id: str, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        cards = items[:8]
        if not cards:
            cards = [{"name": "No KPI", "value": "Not available"}]
        x_positions = [0.7, 5.2]
        y = 1.3
        for idx, item in enumerate(cards):
            col = idx % 2
            if idx and col == 0:
                y += 1.15
            txt = f"{item.get('name', '')}\n{item.get('value', '')}"
            requests.extend(
                self._add_textbox(
                    slide_id,
                    text=txt,
                    x=x_positions[col],
                    y=y,
                    w=3.9,
                    h=1.0,
                    font_size=15,
                    bold=True,
                    color="#0F172A",
                    fill=self.brand.palette.secondary,
                )
            )
        return requests

    def _add_table_slide(self, slide_id: str, table: Dict[str, Any]) -> List[Dict[str, Any]]:
        headers = [str(h) for h in (table.get("headers") or [])]
        rows = table.get("rows") or []
        if not headers:
            return self._add_textbox(
                slide_id,
                text="No tabular data available.",
                x=0.8,
                y=1.6,
                w=8.5,
                h=1.0,
                font_size=16,
                bold=False,
                color="#0F172A",
            )
        row_count = min(12, len(rows) + 1)
        col_count = max(1, min(6, len(headers)))
        table_id = _obj_id("table")
        requests: List[Dict[str, Any]] = [
            {
                "createTable": {
                    "objectId": table_id,
                    "rows": row_count,
                    "columns": col_count,
                    "elementProperties": _element_props(slide_id, 0.7, 1.3, 8.8, 4.9),
                }
            }
        ]
        for c in range(col_count):
            requests.append(
                {
                    "insertText": {
                        "objectId": table_id,
                        "cellLocation": {"rowIndex": 0, "columnIndex": c},
                        "text": self._short(headers[c], 32),
                    }
                }
            )
        for r in range(1, row_count):
            row_values = rows[r - 1] if r - 1 < len(rows) else []
            for c in range(col_count):
                val = row_values[c] if c < len(row_values) else ""
                requests.append(
                    {
                        "insertText": {
                            "objectId": table_id,
                            "cellLocation": {"rowIndex": r, "columnIndex": c},
                            "text": self._short(str(val), 40),
                        }
                    }
                )
        return requests

    def _add_chart_slide(self, slide_id: str, visual: Dict[str, Any]) -> List[Dict[str, Any]]:
        cfg = _chart_config_from_visual(visual)
        url = _quickchart_url(cfg)
        image_id = _obj_id("chart")
        return [
            {
                "createImage": {
                    "objectId": image_id,
                    "url": url,
                    "elementProperties": _element_props(slide_id, 0.8, 1.3, 8.6, 4.9),
                }
            }
        ]

    def _add_textbox(
        self,
        slide_id: str,
        *,
        text: str,
        x: float,
        y: float,
        w: float,
        h: float,
        font_size: int,
        bold: bool,
        color: str,
        fill: str | None = None,
    ) -> List[Dict[str, Any]]:
        object_id = _obj_id("txt")
        reqs: List[Dict[str, Any]] = [
            {
                "createShape": {
                    "objectId": object_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": _element_props(slide_id, x, y, w, h),
                }
            }
        ]
        if fill:
            reqs.append(
                {
                    "updateShapeProperties": {
                        "objectId": object_id,
                        "shapeProperties": {
                            "shapeBackgroundFill": {
                                "solidFill": {"color": {"rgbColor": _rgb(fill)}}
                            },
                            "outline": {"propertyState": "NOT_RENDERED"},
                        },
                        "fields": "shapeBackgroundFill.solidFill.color.rgbColor,outline.propertyState",
                    }
                }
            )
        reqs.extend(
            [
                {
                    "insertText": {
                        "objectId": object_id,
                        "insertionIndex": 0,
                        "text": text,
                    }
                },
                {
                    "updateTextStyle": {
                        "objectId": object_id,
                        "textRange": {"type": "ALL"},
                        "style": {
                            "bold": bold,
                            "fontFamily": "Calibri",
                            "fontSize": {"magnitude": font_size, "unit": "PT"},
                            "foregroundColor": {"opaqueColor": {"rgbColor": _rgb(color)}},
                        },
                        "fields": "bold,fontFamily,fontSize,foregroundColor",
                    }
                },
            ]
        )
        return reqs

    @staticmethod
    def _short(text: str, max_len: int) -> str:
        cleaned = " ".join(text.split())
        return cleaned if len(cleaned) <= max_len else cleaned[: max_len - 3] + "..."

    @staticmethod
    def _wrap(text: str, width: int) -> str:
        normalized = " ".join(str(text).split())
        if len(normalized) <= width:
            return normalized
        chunks = re.findall(rf".{{1,{width}}}(?:\s+|$)", normalized)
        return "\n".join(c.strip() for c in chunks if c.strip())


def _utc_today() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _obj_id(prefix: str) -> str:
    token = uuid.uuid4().hex[:12]
    return f"{prefix}_{token}"


def _element_props(slide_id: str, x: float, y: float, w: float, h: float) -> Dict[str, Any]:
    return {
        "pageObjectId": slide_id,
        "size": {
            "width": {"magnitude": int(w * EMU_PER_INCH), "unit": "EMU"},
            "height": {"magnitude": int(h * EMU_PER_INCH), "unit": "EMU"},
        },
        "transform": {
            "scaleX": 1,
            "scaleY": 1,
            "translateX": int(x * EMU_PER_INCH),
            "translateY": int(y * EMU_PER_INCH),
            "unit": "EMU",
        },
    }


def _rgb(hex_color: str) -> Dict[str, float]:
    c = (hex_color or "#000000").strip().lstrip("#")
    if len(c) != 6:
        c = "000000"
    return {
        "red": int(c[0:2], 16) / 255.0,
        "green": int(c[2:4], 16) / 255.0,
        "blue": int(c[4:6], 16) / 255.0,
    }


def _chart_config_from_visual(visual: Dict[str, Any]) -> Dict[str, Any]:
    data = visual.get("data") or []
    x_key = str(visual.get("x", "label"))
    y_key = str(visual.get("y", "value"))
    labels: List[str] = []
    values: List[float] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        labels.append(str(row.get(x_key, "")))
        raw = str(row.get(y_key, "0")).replace(",", "").replace("%", "")
        try:
            values.append(float(raw))
        except Exception:
            values.append(0.0)
    ctype = str(visual.get("type", "bar")).lower()
    if ctype == "donut":
        ctype = "pie"
    if ctype not in {"bar", "line", "pie", "scatter", "radar", "polarArea", "bubble"}:
        ctype = "bar"
    return {
        "type": ctype,
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": str(visual.get("title", "Metric")),
                    "data": values,
                    "backgroundColor": "#2A9D8F",
                    "borderColor": "#0B3B4C",
                }
            ],
        },
        "options": {
            "plugins": {"legend": {"display": ctype == "pie"}},
            "scales": {
                "x": {"ticks": {"color": "#0F172A"}},
                "y": {"ticks": {"color": "#0F172A"}},
            },
        },
    }


def _quickchart_url(config: Dict[str, Any]) -> str:
    encoded = quote(json.dumps(config, separators=(",", ":")))
    return f"https://quickchart.io/chart?w=1400&h=800&bkg=white&c={encoded}"
