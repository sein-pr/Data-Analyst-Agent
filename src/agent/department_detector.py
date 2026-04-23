from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class DepartmentMatch:
    name: str
    score: int
    matched_keywords: List[str]


def detect_departments(
    columns: List[str],
    *,
    llm_client=None,
    available_departments: Optional[List[str]] = None,
    max_departments: int = 3,
) -> List[DepartmentMatch]:
    allowed = [d.strip().lower() for d in (available_departments or []) if d.strip()]
    if not allowed:
        allowed = ["executive"]

    if llm_client:
        try:
            prompt = _build_prompt(columns, allowed, max_departments)
            raw = llm_client.generate_text(prompt)
            parsed = _parse_department_json(raw, allowed, max_departments)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning("AI department detection failed: %s", exc)

    # Safety fallback: never skip a report if AI classification fails.
    return [DepartmentMatch(name="executive", score=1, matched_keywords=["fallback"])]


def _build_prompt(columns: List[str], allowed: List[str], max_departments: int) -> str:
    cols = [str(c).strip() for c in columns if str(c).strip()]
    return (
        "You are a JSON generator.\n"
        "Your task is to classify which business departments this dataset belongs to.\n\n"
        "STRICT RULES:\n"
        "- Output ONLY JSON\n"
        "- No markdown, no comments, no extra text\n"
        f"- Use only these department names: {allowed}\n"
        f"- Return at most {max_departments} departments\n"
        "- If unsure, include executive as the default\n\n"
        "OUTPUT SCHEMA:\n"
        "{\n"
        '  "departments": [\n'
        '    {"name": "string", "confidence": 0.0, "reasons": ["string"]}\n'
        "  ]\n"
        "}\n\n"
        f"Columns: {cols}\n"
    )


def _parse_department_json(raw: str, allowed: List[str], max_departments: int) -> List[DepartmentMatch]:
    payload = _extract_json(raw)
    if not payload:
        return []

    items = payload.get("departments")
    if not isinstance(items, list):
        return []

    matches: List[DepartmentMatch] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower()
        if name not in allowed:
            continue
        confidence = item.get("confidence", 0.5)
        try:
            conf = float(confidence)
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        reasons = item.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = []
        reasons = [str(r).strip() for r in reasons if str(r).strip()]
        matches.append(
            DepartmentMatch(
                name=name,
                score=int(conf * 100),
                matched_keywords=reasons[:5],
            )
        )

    deduped: List[DepartmentMatch] = []
    seen = set()
    for match in sorted(matches, key=lambda m: m.score, reverse=True):
        if match.name in seen:
            continue
        deduped.append(match)
        seen.add(match.name)
        if len(deduped) >= max_departments:
            break
    return deduped


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None
