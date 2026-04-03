from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisRecord:
    dataset_name: str
    schema_signature: str
    kpis: Dict[str, Any]
    top_products: Any
    outliers: Any
    created_at: str


class SupabaseStore:
    def __init__(self, url: str, key: str, table: str = "analysis_history") -> None:
        from supabase import create_client

        self.client = create_client(url, key)
        self.table = table

    def fetch_latest(self, schema_signature: str) -> Optional[Dict[str, Any]]:
        try:
            response = (
                self.client.table(self.table)
                .select("*")
                .eq("schema_signature", schema_signature)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            data = response.data or []
            return data[0] if data else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase fetch failed: %s", exc)
            return None

    def insert(self, record: Dict[str, Any]) -> None:
        try:
            self.client.table(self.table).insert(record).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase insert failed: %s", exc)
