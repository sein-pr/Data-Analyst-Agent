from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from pydantic import BaseModel, ValidationError

from .logger import get_logger

logger = get_logger(__name__)


class CleaningInstruction(BaseModel):
    column: str = ""
    operation: str = ""
    value: Any = None
    new_name: str = ""


class KPIDefinition(BaseModel):
    name: str
    columns: List[str]
    aggregation: str
    description: str = ""


class DiscoveryPayload(BaseModel):
    domain: str
    kpis: List[KPIDefinition]
    cleaning_instructions: List[CleaningInstruction]
    confidence: float


@dataclass
class DiscoveryResult:
    domain: str
    kpis: List[Dict[str, Any]]
    cleaning_instructions: List[Dict[str, Any]]
    confidence: float
    schema_fingerprint: str
    cache_hit: bool

    @property
    def is_confident(self) -> bool:
        return bool(self.kpis) and self.confidence >= 0.5


class SchemaDiscoveryService:
    def __init__(self, llm_client: object | None, cache_dir: Path | None = None) -> None:
        self.llm_client = llm_client
        self.cache_dir = cache_dir or Path("state/discovery_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def discover(self, df: pd.DataFrame) -> DiscoveryResult:
        fingerprint = self._build_fingerprint(df)
        cached = self._load_cache(fingerprint)
        if cached:
            return DiscoveryResult(
                domain=cached.get("domain", "Unknown"),
                kpis=cached.get("kpis", []),
                cleaning_instructions=cached.get("cleaning_instructions", []),
                confidence=float(cached.get("confidence", 0.0)),
                schema_fingerprint=fingerprint,
                cache_hit=True,
            )

        if not self.llm_client:
            fallback = self._heuristic_discovery(df)
            self._save_cache(fingerprint, fallback)
            return DiscoveryResult(
                domain=fallback["domain"],
                kpis=fallback["kpis"],
                cleaning_instructions=fallback["cleaning_instructions"],
                confidence=float(fallback.get("confidence", 0.6)),
                schema_fingerprint=fingerprint,
                cache_hit=False,
            )

        prompt = self._build_prompt(df)
        raw = self.llm_client.generate_text(prompt)
        parsed = self._parse_discovery_payload(raw)
        if not parsed:
            logger.warning("Schema discovery failed to parse valid JSON payload.")
            return DiscoveryResult(
                domain="Unknown",
                kpis=[],
                cleaning_instructions=[],
                confidence=0.0,
                schema_fingerprint=fingerprint,
                cache_hit=False,
            )

        data = {
            "domain": parsed.domain,
            "kpis": [k.model_dump() for k in parsed.kpis],
            "cleaning_instructions": [c.model_dump() for c in parsed.cleaning_instructions],
            "confidence": float(parsed.confidence),
        }
        self._save_cache(fingerprint, data)
        return DiscoveryResult(
            domain=data["domain"],
            kpis=data["kpis"],
            cleaning_instructions=data["cleaning_instructions"],
            confidence=data["confidence"],
            schema_fingerprint=fingerprint,
            cache_hit=False,
        )

    def apply_cleaning(
        self,
        df: pd.DataFrame,
        instructions: List[Dict[str, Any]],
    ) -> Tuple[pd.DataFrame, List[str]]:
        cleaned = df.copy()
        warnings: List[str] = []
        for instruction in instructions:
            column = str(instruction.get("column", "")).strip()
            operation = str(instruction.get("operation", "")).strip().lower()
            value = instruction.get("value")
            new_name = str(instruction.get("new_name", "")).strip()
            if not operation:
                continue
            if operation == "rename":
                if column in cleaned.columns and new_name:
                    cleaned = cleaned.rename(columns={column: new_name})
                else:
                    warnings.append(f"Rename skipped: {column} -> {new_name}")
                continue
            if column not in cleaned.columns:
                warnings.append(f"Column not found for operation {operation}: {column}")
                continue
            try:
                if operation == "to_numeric":
                    cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
                elif operation == "to_datetime":
                    cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce")
                elif operation == "fillna":
                    cleaned[column] = cleaned[column].fillna(value)
                elif operation == "strip_currency":
                    cleaned[column] = (
                        cleaned[column]
                        .astype(str)
                        .str.replace(r"[^0-9.\-]", "", regex=True)
                    )
                    cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
                elif operation == "lowercase":
                    cleaned[column] = cleaned[column].astype(str).str.lower()
                elif operation == "uppercase":
                    cleaned[column] = cleaned[column].astype(str).str.upper()
                else:
                    warnings.append(f"Unknown cleaning operation: {operation}")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Cleaning failed for {column} ({operation}): {exc}")
        return cleaned, warnings

    def _build_prompt(self, df: pd.DataFrame) -> str:
        sample = df.head(8).astype(str).to_dict(orient="records")
        dtypes = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
        return (
            "You are a JSON generator.\n"
            "Return ONLY valid JSON. No markdown, no commentary.\n\n"
            "STRICT RULES:\n"
            "- Output ONLY JSON\n"
            "- No text before or after JSON\n"
            "- Use double quotes for keys and strings\n"
            "- Ensure parsable JSON\n\n"
            "TASK:\n"
            "Infer dataset business domain, propose 3-5 KPIs, and provide semantic cleaning instructions.\n"
            "If uncertain, lower confidence and keep KPI list empty.\n\n"
            "JSON SCHEMA:\n"
            "{\n"
            "  \"domain\": \"string\",\n"
            "  \"kpis\": [\n"
            "    {\n"
            "      \"name\": \"string\",\n"
            "      \"columns\": [\"string\"],\n"
            "      \"aggregation\": \"sum|avg|count|min|max|ratio|count_distinct\",\n"
            "      \"description\": \"string\"\n"
            "    }\n"
            "  ],\n"
            "  \"cleaning_instructions\": [\n"
            "    {\n"
            "      \"column\": \"string\",\n"
            "      \"operation\": \"to_numeric|to_datetime|fillna|strip_currency|rename|lowercase|uppercase\",\n"
            "      \"value\": \"any\",\n"
            "      \"new_name\": \"string\"\n"
            "    }\n"
            "  ],\n"
            "  \"confidence\": 0.0\n"
            "}\n\n"
            f"Columns: {list(map(str, df.columns.tolist()))}\n"
            f"Dtypes: {dtypes}\n"
            f"Sample rows: {sample}\n"
        )

    def _heuristic_discovery(self, df: pd.DataFrame) -> Dict[str, Any]:
        numeric_cols = [str(col) for col in df.select_dtypes(include="number").columns.tolist()]
        kpis: List[Dict[str, Any]] = []
        for col in numeric_cols[:5]:
            kpis.append(
                {
                    "name": f"Total {col}",
                    "columns": [col],
                    "aggregation": "sum",
                    "description": f"Total value for {col}.",
                }
            )
        return {
            "domain": "General Business",
            "kpis": kpis,
            "cleaning_instructions": [],
            "confidence": 0.6 if kpis else 0.3,
        }

    def _build_fingerprint(self, df: pd.DataFrame) -> str:
        columns = [str(c).strip().lower() for c in df.columns.tolist()]
        dtype_map = {str(col).strip().lower(): str(dtype) for col, dtype in df.dtypes.items()}
        sample_csv = df.head(3).to_csv(index=False)
        payload = json.dumps(
            {"columns": columns, "dtypes": dtype_map, "sample": sample_csv},
            sort_keys=True,
        )
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, fingerprint: str) -> Path:
        return self.cache_dir / f"{fingerprint}.json"

    def _load_cache(self, fingerprint: str) -> Dict[str, Any] | None:
        path = self._cache_path(fingerprint)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

    def _save_cache(self, fingerprint: str, payload: Dict[str, Any]) -> None:
        path = self._cache_path(fingerprint)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _parse_discovery_payload(self, raw_text: str) -> DiscoveryPayload | None:
        data = self._extract_json(raw_text)
        if not isinstance(data, dict):
            return None
        try:
            payload = DiscoveryPayload.model_validate(data)
        except ValidationError:
            return None
        if payload.confidence < 0:
            payload.confidence = 0.0
        if payload.confidence > 1:
            payload.confidence = 1.0
        return payload

    @staticmethod
    def _extract_json(raw_text: str) -> Dict[str, Any] | None:
        if not raw_text:
            return None
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        try:
            return json.loads(stripped)
        except Exception:
            pass
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
