from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..logger import get_logger

logger = get_logger(__name__)


def plan_visuals(analysis_payload: Dict[str, object], llm_client=None) -> List[Dict[str, str]]:
    candidates = []
    if analysis_payload.get("monthly_revenue"):
        candidates.append(
            {
                "id": "monthly_revenue",
                "title": "Revenue Trend (Monthly)",
                "type": "line",
                "x": "Month",
                "y": "Revenue",
                "data": analysis_payload.get("monthly_revenue", []),
            }
        )
    if analysis_payload.get("top_products"):
        candidates.append(
            {
                "id": "top_products",
                "title": "Top Products by Revenue",
                "type": "bar",
                "x": "Product Category",
                "y": "Revenue",
                "data": analysis_payload.get("top_products", []),
            }
        )
    if analysis_payload.get("revenue_by_channel"):
        candidates.append(
            {
                "id": "revenue_by_channel",
                "title": "Revenue by Channel",
                "type": "bar",
                "x": "Channel",
                "y": "Revenue",
                "data": analysis_payload.get("revenue_by_channel", []),
            }
        )
    if analysis_payload.get("revenue_by_region"):
        candidates.append(
            {
                "id": "revenue_by_region",
                "title": "Revenue by Region",
                "type": "bar",
                "x": "Region",
                "y": "Revenue",
                "data": analysis_payload.get("revenue_by_region", []),
            }
        )

    if not candidates:
        return []

    if not llm_client:
        return candidates[:2]

    prompt = (
        "You are a visual analytics planner. Select up to two visuals that best explain the data.\n"
        "Choose chart types from: bar, line, pie, donut, scatter.\n"
        "STRICT RULES:\n"
        "- Output ONLY JSON\n"
        "- NO TEXT BEFORE/AFTER JSON\n"
        "- Do NOT include markdown (no ```json)\n"
        "- Do NOT include comments\n"
        "Return strict JSON in the form {\"charts\": [{\"id\": \"...\", \"type\": \"bar\"}]}\n"
        f"Candidates: {json.dumps(candidates)}"
    )
    try:
        response = llm_client.generate_text(prompt)
        data = json.loads(response)
        charts = data.get("charts", [])
        selected = []
        for item in charts:
            chart_id = item.get("id")
            chart_type = item.get("type")
            for cand in candidates:
                if cand["id"] == chart_id:
                    selected.append({**cand, "type": chart_type or cand["type"]})
        return selected[:2] if selected else candidates[:2]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Visual planner failed; using defaults. %s", exc)
        return candidates[:2]
