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
        return _fallback_plan(candidates, department=department)

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
    return _fallback_plan(candidates, department=department)


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


def _fallback_plan(candidates: List[Dict[str, Any]], *, department: str) -> List[Dict[str, Any]]:
    by_kind: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_kind.setdefault(c["kind"], []).append(c)

    dept = (department or "executive").strip().lower()
    chart_priority = {
        "finance": ["chart_monthly_revenue", "chart_top_products", "chart_revenue_by_region", "chart_revenue_by_channel"],
        "marketing": ["chart_revenue_by_channel", "chart_monthly_revenue", "chart_top_products", "chart_revenue_by_region"],
        "sales": ["chart_top_products", "chart_monthly_revenue", "chart_revenue_by_region", "chart_revenue_by_channel"],
        "executive": ["chart_monthly_revenue", "chart_top_products", "chart_revenue_by_channel", "chart_revenue_by_region"],
    }
    table_priority = {
        "finance": ["table_outliers", "table_top_products", "table_revenue_by_region", "table_revenue_by_channel"],
        "marketing": ["table_revenue_by_channel", "table_top_products", "table_revenue_by_region", "table_outliers"],
        "sales": ["table_top_products", "table_revenue_by_region", "table_revenue_by_channel", "table_outliers"],
        "executive": ["table_top_products", "table_outliers", "table_revenue_by_channel", "table_revenue_by_region"],
    }
    by_id = {str(c.get("id", "")): c for c in candidates}

    plan: List[Dict[str, Any]] = []
    if by_kind.get("title"):
        plan.append(by_kind["title"][0])

    # Lead with narrative before KPI tiles so decks don't all look the same.
    for cid in ["bullets_executive_summary", "bullets_key_findings"]:
        if cid in by_id:
            plan.append(by_id[cid])
            break

    if by_kind.get("kpi_cards"):
        plan.append(by_kind["kpi_cards"][0])

    # Pick up to 3 department-prioritized charts
    added_chart_ids = set()
    for cid in chart_priority.get(dept, chart_priority["executive"]):
        if cid in by_id and cid not in added_chart_ids:
            plan.append(by_id[cid])
            added_chart_ids.add(cid)
        if len(added_chart_ids) >= 3:
            break
    if len(added_chart_ids) < 2:
        for c in by_kind.get("chart", []):
            cid = str(c.get("id", ""))
            if cid in added_chart_ids:
                continue
            plan.append(c)
            added_chart_ids.add(cid)
            if len(added_chart_ids) >= 3:
                break

    # Pick one table by department intent
    picked_table = False
    for cid in table_priority.get(dept, table_priority["executive"]):
        if cid in by_id:
            plan.append(by_id[cid])
            picked_table = True
            break
    if not picked_table and by_kind.get("table"):
        plan.append(by_kind["table"][0])

    # Add curated narrative slides
    for cid in [
        "bullets_insights_interpretation",
        "bullets_recommendations",
        "bullets_risks_limitations",
        "bullets_next_steps",
        "bullets_objectives",
    ]:
        if cid in by_id:
            plan.append(by_id[cid])

    # Fill with any remaining bullets if still short
    chosen_ids = {str(s.get("id", "")) for s in plan}
    for b in by_kind.get("bullets", []):
        bid = str(b.get("id", ""))
        if bid in chosen_ids:
            continue
        plan.append(b)
        chosen_ids.add(bid)
        if len(plan) >= 12:
            break

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
