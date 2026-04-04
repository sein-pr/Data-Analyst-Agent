from __future__ import annotations

import json
from typing import Dict, List

from ..logger import get_logger

logger = get_logger(__name__)


def select_kpis(kpis: Dict[str, str], llm_client=None, limit: int = 6) -> List[str]:
    if not kpis:
        return []
    keys = list(kpis.keys())
    if not llm_client:
        return keys[:limit]
    prompt = (
        "You are an executive analyst. Select the most important KPIs to show on a dashboard.\n"
        f"Return strict JSON: {{\"kpis\": [\"kpi1\", \"kpi2\"]}}. Limit {limit}.\n"
        f"Available KPIs: {keys}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = json.loads(response)
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
        "You are a business analyst. Write a short, executive-friendly description for each KPI.\n"
        "Return strict JSON: {\"descriptions\": {\"KPI Name\": \"short description\"}}\n"
        f"KPIs: {[name for name, _ in kpi_items]}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = json.loads(response)
        descriptions = data.get("descriptions", {})
        return {name: str(descriptions.get(name, "")) for name, _ in kpi_items}
    except Exception as exc:  # noqa: BLE001
        logger.warning("KPI description failed; using defaults. %s", exc)
        return {name: "Key performance indicator for the dashboard." for name, _ in kpi_items}
