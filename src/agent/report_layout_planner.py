from __future__ import annotations

import json
from typing import Any, Dict, List

from .logger import get_logger

logger = get_logger(__name__)


def plan_report_layout(
    *,
    sections: Dict[str, List[str]],
    kpis: Dict[str, str],
    selected_kpis: List[str],
    selected_visuals: List[Dict[str, Any]],
    top_products: List[Dict[str, str]],
    outliers: List[Dict[str, str]],
    revenue_by_channel: List[Dict[str, str]],
    revenue_by_region: List[Dict[str, str]],
    department: str,
    llm_client=None,
) -> List[Dict[str, Any]]:
    candidates = _build_candidates(
        sections=sections,
        kpis=kpis,
        selected_kpis=selected_kpis,
        selected_visuals=selected_visuals,
        top_products=top_products,
        outliers=outliers,
        revenue_by_channel=revenue_by_channel,
        revenue_by_region=revenue_by_region,
        department=department,
    )
    if not llm_client:
        return _fallback_plan(candidates)

    prompt = (
        "You are a presentation layout planner.\n"
        "Output ONLY valid JSON. No markdown, no prose.\n\n"
        "GOAL:\n"
        "- Build a non-generic slide flow for an executive deck.\n"
        "- Prioritize the most informative visuals/tables for this specific dataset.\n"
        "- Avoid repeating the same content type across too many slides.\n\n"
        "RULES:\n"
        "- Max 12 slides\n"
        "- Must include exactly one 'title' slide\n"
        "- Must include at least one 'chart' or one 'table' slide\n"
        "- Use only candidate IDs provided\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "slides": [\n'
        "    {\n"
        '      "kind": "title|bullets|kpi_cards|table|chart",\n'
        '      "title": "string",\n'
        '      "candidate_id": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Department: {department}\n"
        f"Candidates: {json.dumps(candidates)}\n"
    )
    try:
        raw = llm_client.generate_text(prompt)
        data = _extract_json(raw)
        slides = data.get("slides", []) if isinstance(data, dict) else []
        planned: List[Dict[str, Any]] = []
        by_id = {c["id"]: c for c in candidates}
        for slide in slides:
            candidate_id = str(slide.get("candidate_id", "")).strip()
            if not candidate_id or candidate_id not in by_id:
                continue
            base = by_id[candidate_id]
            planned.append(
                {
                    "kind": slide.get("kind") or base.get("kind"),
                    "title": slide.get("title") or base.get("title"),
                    **base,
                }
            )
        validated = _validate_plan(planned)
        if validated:
            return validated
    except Exception as exc:  # noqa: BLE001
        logger.warning("Report layout planner failed; using fallback. %s", exc)
    return _fallback_plan(candidates)


def _build_candidates(
    *,
    sections: Dict[str, List[str]],
    kpis: Dict[str, str],
    selected_kpis: List[str],
    selected_visuals: List[Dict[str, Any]],
    top_products: List[Dict[str, str]],
    outliers: List[Dict[str, str]],
    revenue_by_channel: List[Dict[str, str]],
    revenue_by_region: List[Dict[str, str]],
    department: str,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    candidates.append(
        {
            "id": "title",
            "kind": "title",
            "title": f"{department.title()} Executive Report",
            "bullets": sections.get("executive_summary", [])[:2],
        }
    )
    for key, title in [
        ("executive_summary", "Executive Highlights"),
        ("objectives", "Objectives"),
        ("key_findings", "Key Findings"),
        ("insights_interpretation", "Insights and Interpretation"),
        ("recommendations", "Recommendations"),
        ("risks_limitations", "Risks and Limitations"),
        ("next_steps", "Next Steps"),
    ]:
        items = sections.get(key, [])
        if items:
            candidates.append(
                {
                    "id": f"bullets_{key}",
                    "kind": "bullets",
                    "title": title,
                    "bullets": items[:8],
                }
            )

    if kpis:
        ordered = selected_kpis or list(kpis.keys())[:8]
        kpi_items = [{"name": k, "value": str(kpis.get(k, ""))} for k in ordered if k in kpis]
        if kpi_items:
            candidates.append(
                {
                    "id": "kpi_cards_main",
                    "kind": "kpi_cards",
                    "title": "AI-Selected KPI Highlights",
                    "kpi_items": kpi_items[:8],
                }
            )

    for visual in selected_visuals:
        vid = str(visual.get("id", "")).strip()
        if not vid:
            continue
        candidates.append(
            {
                "id": f"chart_{vid}",
                "kind": "chart",
                "title": visual.get("title", "Chart"),
                "visual": visual,
            }
        )

    for table_id, title, rows in [
        ("top_products", "Top Products Table", _to_rows(top_products)),
        ("outliers", "Outliers Table", _to_rows(outliers)),
        ("revenue_by_channel", "Revenue by Channel Table", _to_rows(revenue_by_channel)),
        ("revenue_by_region", "Revenue by Region Table", _to_rows(revenue_by_region)),
    ]:
        if not rows:
            continue
        headers = list(rows[0].keys())
        values = [[str(r.get(h, "")) for h in headers] for r in rows[:10]]
        candidates.append(
            {
                "id": f"table_{table_id}",
                "kind": "table",
                "title": title,
                "table": {
                    "headers": headers,
                    "rows": values,
                },
            }
        )
    return candidates


def _fallback_plan(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_kind.setdefault(c["kind"], []).append(c)

    plan: List[Dict[str, Any]] = []
    if by_kind.get("title"):
        plan.append(by_kind["title"][0])
    if by_kind.get("kpi_cards"):
        plan.append(by_kind["kpi_cards"][0])
    # Pick up to 2 different charts
    plan.extend(by_kind.get("chart", [])[:2])
    # Pick one high-value table
    if by_kind.get("table"):
        plan.append(by_kind["table"][0])
    # Add narrative slides last
    plan.extend(by_kind.get("bullets", [])[:5])
    validated = _validate_plan(plan[:12])
    return validated


def _validate_plan(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not plan:
        return []
    title_count = sum(1 for s in plan if s.get("kind") == "title")
    if title_count == 0:
        plan.insert(
            0,
            {"id": "title_auto", "kind": "title", "title": "Executive Report", "bullets": []},
        )
    elif title_count > 1:
        kept = []
        seen_title = False
        for slide in plan:
            if slide.get("kind") == "title":
                if seen_title:
                    continue
                seen_title = True
            kept.append(slide)
        plan = kept
    has_visual = any(s.get("kind") in {"chart", "table"} for s in plan)
    if not has_visual:
        for slide in plan:
            if slide.get("kind") == "kpi_cards":
                # still allow if no visual available
                return plan[:12]
    return plan[:12]


def _to_rows(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not items:
        return []
    return [dict((str(k), str(v)) for k, v in row.items()) for row in items]


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(stripped[start : end + 1])
    except Exception:
        return {}
