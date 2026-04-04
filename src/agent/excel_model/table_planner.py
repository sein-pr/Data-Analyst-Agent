from __future__ import annotations

import json
from typing import Dict, List

from ..logger import get_logger

logger = get_logger(__name__)


def plan_tables(analysis_payload: Dict[str, object], llm_client=None) -> List[Dict[str, object]]:
    candidates = []
    if analysis_payload.get("top_products"):
        candidates.append(
            {
                "id": "top_products",
                "title": "Top Products",
                "headers": ["Product Category", "Revenue"],
                "rows": _rows_from_dicts(analysis_payload.get("top_products", []), ["Product Category", "Revenue"]),
            }
        )
    if analysis_payload.get("outliers"):
        candidates.append(
            {
                "id": "outliers",
                "title": "Outliers",
                "headers": ["Product Category", "Revenue"],
                "rows": _rows_from_dicts(analysis_payload.get("outliers", []), ["Product Category", "Revenue"]),
            }
        )
    if analysis_payload.get("revenue_by_channel"):
        candidates.append(
            {
                "id": "revenue_by_channel",
                "title": "Revenue by Channel",
                "headers": ["Channel", "Revenue"],
                "rows": _rows_from_dicts(analysis_payload.get("revenue_by_channel", []), ["Channel", "Revenue"]),
            }
        )
    if analysis_payload.get("revenue_by_region"):
        candidates.append(
            {
                "id": "revenue_by_region",
                "title": "Revenue by Region",
                "headers": ["Region", "Revenue"],
                "rows": _rows_from_dicts(analysis_payload.get("revenue_by_region", []), ["Region", "Revenue"]),
            }
        )

    if not candidates:
        return []

    if not llm_client:
        return candidates[:2]

    prompt = (
        "You are a dashboard planner. Select up to two tables to show.\n"
        "Return strict JSON: {\"tables\": [\"id1\", \"id2\"]}\n"
        f"Candidates: {[c['id'] for c in candidates]}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = json.loads(response)
        selected_ids = data.get("tables", [])
        selected = [c for c in candidates if c["id"] in selected_ids]
        return selected[:2] if selected else candidates[:2]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Table planner failed; using defaults. %s", exc)
        return candidates[:2]


def _rows_from_dicts(items: List[Dict[str, object]], keys: List[str]) -> List[List[object]]:
    rows = []
    for item in items:
        rows.append([item.get(k, "") for k in keys])
    return rows
