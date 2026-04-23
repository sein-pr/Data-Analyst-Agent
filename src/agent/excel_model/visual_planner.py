from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..logger import get_logger

logger = get_logger(__name__)


def plan_visuals(
    analysis_payload: Dict[str, object],
    llm_client=None,
    *,
    department: str | None = None,
    limit: int = 3,
) -> List[Dict[str, object]]:
    candidates = _build_candidates(analysis_payload)
    if not candidates:
        return []

    if not llm_client:
        return _fallback_pick(candidates, department=department, limit=limit)

    prompt = (
        "You are a visual analytics planner.\n"
        "Choose the strongest visuals for this specific department and dataset.\n"
        "Avoid repetitive chart choices across slides.\n\n"
        "STRICT RULES:\n"
        "- Output ONLY valid JSON\n"
        "- NO TEXT BEFORE/AFTER JSON\n"
        "- No markdown code fences\n"
        "- No comments\n"
        f"- Return at most {limit} visuals\n\n"
        "JSON schema:\n"
        "{\n"
        '  "charts": [\n'
        "    {\n"
        '      "id": "candidate_id",\n'
        '      "type": "bar|line|pie|donut|scatter",\n'
        '      "title": "optional override title"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Department: {department or 'executive'}\n"
        f"Candidates: {json.dumps(candidates)}\n"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = _extract_json(response)
        charts = data.get("charts", []) if isinstance(data, dict) else []
        selected: List[Dict[str, object]] = []
        by_id = {str(c.get("id", "")): c for c in candidates}
        for item in charts:
            if not isinstance(item, dict):
                continue
            chart_id = str(item.get("id", "")).strip()
            chart_type = str(item.get("type", "")).strip().lower()
            if chart_id not in by_id:
                continue
            base = dict(by_id[chart_id])
            if chart_type in {"bar", "line", "pie", "donut", "scatter"}:
                base["type"] = chart_type
            title = str(item.get("title", "")).strip()
            if title:
                base["title"] = title
            selected.append(base)
            if len(selected) >= limit:
                break
        if selected:
            return _dedupe(selected)[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Visual planner failed; using adaptive fallback. %s", exc)

    return _fallback_pick(candidates, department=department, limit=limit)


def _build_candidates(analysis_payload: Dict[str, object]) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    explicit = {
        "monthly_revenue": ("Revenue Trend (Monthly)", "line", "Month", "Revenue"),
        "top_products": ("Top Products by Revenue", "bar", "Product Category", "Revenue"),
        "revenue_by_channel": ("Revenue by Channel", "bar", "Channel", "Revenue"),
        "revenue_by_region": ("Revenue by Region", "bar", "Region", "Revenue"),
        "outliers": ("Outlier Revenue Distribution", "scatter", "Product Category", "Revenue"),
    }
    for key, (title, chart_type, x_key, y_key) in explicit.items():
        rows = analysis_payload.get(key) or []
        if _is_rowset(rows):
            candidates.append(
                {
                    "id": key,
                    "source": key,
                    "title": title,
                    "type": chart_type,
                    "x": _resolve_axis(rows, preferred=x_key, fallback_index=0),
                    "y": _resolve_axis(rows, preferred=y_key, fallback_index=1, numeric_preferred=True),
                    "data": rows,
                    "rows": len(rows),
                }
            )

    # Generic discovery: include any additional rowset from payload that can be charted.
    for key, value in analysis_payload.items():
        if key in explicit:
            continue
        if not _is_rowset(value):
            continue
        rows = value
        if len(rows) < 2:
            continue
        x_col = _resolve_axis(rows, fallback_index=0)
        y_col = _resolve_axis(rows, fallback_index=1, numeric_preferred=True)
        if not x_col or not y_col:
            continue
        chart_type = _suggest_chart_type(x_col, y_col, rows)
        candidates.append(
            {
                "id": str(key),
                "source": str(key),
                "title": _titleize(str(key)),
                "type": chart_type,
                "x": x_col,
                "y": y_col,
                "data": rows,
                "rows": len(rows),
            }
        )
    return _dedupe(candidates)


def _fallback_pick(
    candidates: List[Dict[str, object]],
    *,
    department: str | None,
    limit: int,
) -> List[Dict[str, object]]:
    dept = (department or "executive").strip().lower()
    priority_map = {
        "finance": ["monthly_revenue", "top_products", "revenue_by_region", "outliers", "revenue_by_channel"],
        "marketing": ["revenue_by_channel", "monthly_revenue", "top_products", "revenue_by_region"],
        "sales": ["top_products", "monthly_revenue", "revenue_by_region", "revenue_by_channel"],
        "executive": ["monthly_revenue", "top_products", "revenue_by_channel", "revenue_by_region", "outliers"],
    }
    preferred = priority_map.get(dept, priority_map["executive"])
    by_id = {str(c.get("id", "")): c for c in candidates}
    selected: List[Dict[str, object]] = []
    for cid in preferred:
        if cid in by_id:
            selected.append(dict(by_id[cid]))
        if len(selected) >= limit:
            return selected[:limit]
    for cand in candidates:
        if any(c.get("id") == cand.get("id") for c in selected):
            continue
        selected.append(dict(cand))
        if len(selected) >= limit:
            break
    return selected[:limit]


def _dedupe(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    unique: List[Dict[str, object]] = []
    for item in items:
        key = str(item.get("id", "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _extract_json(text: str) -> Dict[str, object]:
    raw = (text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}
    return {}


def _is_rowset(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    return isinstance(value[0], dict)


def _resolve_axis(
    rows: List[Dict[str, object]],
    *,
    preferred: str | None = None,
    fallback_index: int = 0,
    numeric_preferred: bool = False,
) -> str:
    first = rows[0] if rows else {}
    keys = [str(k) for k in first.keys()]
    if preferred and preferred in keys:
        return preferred
    if not keys:
        return ""
    if numeric_preferred:
        for k in keys:
            if _looks_numeric_column(rows, k):
                return k
    idx = max(0, min(fallback_index, len(keys) - 1))
    return keys[idx]


def _looks_numeric_column(rows: List[Dict[str, object]], col: str) -> bool:
    numeric = 0
    total = 0
    for row in rows[:15]:
        if col not in row:
            continue
        total += 1
        value = str(row.get(col, "")).replace(",", "").replace("%", "").strip()
        if not value:
            continue
        try:
            float(value)
            numeric += 1
        except Exception:
            continue
    return total > 0 and (numeric / total) >= 0.6


def _suggest_chart_type(x_col: str, y_col: str, rows: List[Dict[str, object]]) -> str:
    x_name = x_col.lower()
    if "date" in x_name or "month" in x_name or "week" in x_name or "year" in x_name:
        return "line"
    if len(rows) <= 6:
        return "donut"
    if _looks_numeric_column(rows, x_col) and _looks_numeric_column(rows, y_col):
        return "scatter"
    return "bar"


def _titleize(raw: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", raw).strip()
    return " ".join(w.capitalize() for w in cleaned.split()) or "Chart"
