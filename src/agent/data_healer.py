from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class MappingResult:
    mapping: Dict[str, str]
    unmapped_required: List[str]
    new_columns: List[str]


class DataHealer:
    def __init__(self, required_columns: Sequence[str], llm_client=None) -> None:
        self.required_columns = list(required_columns)
        self.llm_client = llm_client

    def map_columns(self, raw_headers: Iterable[str]) -> MappingResult:
        raw_headers_list = list(raw_headers)
        mapping = self._heuristic_map(raw_headers_list)
        unmapped = [col for col in self.required_columns if col not in mapping.values()]

        if unmapped and self.llm_client:
            logger.info("Attempting LLM-based column mapping for: %s", unmapped)
            try:
                llm_mapping = self.llm_client.map_columns(self.required_columns, raw_headers_list)
                mapping.update(llm_mapping)
                unmapped = [col for col in self.required_columns if col not in mapping.values()]
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM mapping failed; using heuristic mapping only. %s", exc)

        new_columns = [col for col in raw_headers_list if col not in mapping.keys()]
        return MappingResult(mapping=mapping, unmapped_required=unmapped, new_columns=new_columns)

    def _heuristic_map(self, raw_headers: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        normalized = {self._normalize(col): col for col in raw_headers}
        for target in self.required_columns:
            target_norm = self._normalize(target)
            if target_norm in normalized:
                mapping[normalized[target_norm]] = target
                continue
            close = difflib.get_close_matches(target_norm, normalized.keys(), n=1, cutoff=0.7)
            if close:
                mapping[normalized[close[0]]] = target
        return mapping

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(ch for ch in text.lower() if ch.isalnum())
