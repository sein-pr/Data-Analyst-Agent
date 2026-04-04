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
