from __future__ import annotations

import json
import re
from typing import Dict, List

from ..logger import get_logger

logger = get_logger(__name__)


def select_kpis(
    kpis: Dict[str, str],
    llm_client=None,
    limit: int = 6,
    department: str | None = None,
) -> List[str]:
    if not kpis:
        return []
    keys = list(kpis.keys())
    if not llm_client:
        return keys[:limit]
    dept_hint = f"Department: {department}. " if department else ""
    prompt = (
        "You are a JSON generator.\n"
        "Select the most important KPIs to show on a dashboard.\n"
        "Return ONLY valid JSON. No markdown, no comments, no extra text.\n"
        f"{dept_hint}"
        f"Return strict JSON: {{\"kpis\": [\"kpi1\", \"kpi2\"]}}. Limit {limit}.\n"
        f"Available KPIs: {keys}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = _parse_json_object(response)
        selection = [k for k in data.get("kpis", []) if k in kpis]
        return selection[:limit] if selection else keys[:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("KPI selection failed; using defaults. %s", exc)
        return keys[:limit]


def describe_kpis(kpi_items: List[tuple[str, str]], llm_client=None) -> Dict[str, str]:
    if not kpi_items:
        return {}
    if not llm_client:
        return {name: "Key performance indicator for the dashboard." for name, _ in kpi_items}
    prompt = (
        "You are a JSON generator.\n"
        "Write a short, executive-friendly description for each KPI.\n"
        "Return ONLY valid JSON. No markdown, no comments, no extra text.\n"
        "Return strict JSON: {\"descriptions\": {\"KPI Name\": \"short description\"}}\n"
        f"KPIs: {[name for name, _ in kpi_items]}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = _parse_json_object(response)
        descriptions = data.get("descriptions", {})
        return {
            name: str(descriptions.get(name) or "Key performance indicator for the dashboard.")
            for name, _ in kpi_items
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("KPI description failed; using defaults. %s", exc)
        return {name: "Key performance indicator for the dashboard." for name, _ in kpi_items}


def _parse_json_object(text: str) -> Dict[str, object]:
    raw = (text or "").strip()
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
        raise ValueError("No JSON object found in model response.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")
    return parsed
