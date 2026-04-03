from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DepartmentMatch:
    name: str
    score: int
    matched_keywords: List[str]


DEPARTMENT_KEYWORDS: Dict[str, List[str]] = {
    "executive": ["strategy", "risk", "opportunity", "portfolio"],
    "finance": [
        "revenue",
        "profit",
        "margin",
        "cost",
        "expense",
        "cogs",
        "opex",
        "capex",
        "ebitda",
        "cash",
        "ar",
        "ap",
        "balance",
    ],
    "sales": [
        "deal",
        "pipeline",
        "stage",
        "opportunity",
        "quota",
        "rep",
        "territory",
        "win",
        "close",
        "booking",
        "arr",
        "mrr",
        "acv",
    ],
    "marketing": [
        "campaign",
        "channel",
        "ctr",
        "cpc",
        "cpm",
        "conversion",
        "impression",
        "click",
        "lead",
        "roas",
        "spend",
        "traffic",
        "email",
        "social",
    ],
}


def detect_departments(columns: List[str], min_score: int = 2) -> List[DepartmentMatch]:
    normalized = " ".join([col.lower() for col in columns])
    matches: List[DepartmentMatch] = []
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in normalized]
        score = len(matched)
        if score >= min_score:
            matches.append(DepartmentMatch(name=dept, score=score, matched_keywords=matched))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches
