from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote_plus, urlparse

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
    def __init__(
        self,
        url: str,
        key: str,
        table: str = "analysis_history",
        db_password: Optional[str] = None,
        allow_dynamic_columns: bool = True,
    ) -> None:
        from supabase import create_client

        self.client = create_client(url, key)
        self.url = url
        self.table = table
        self.db_password = db_password
        self.allow_dynamic_columns = allow_dynamic_columns

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
        payload = dict(record)
        for _ in range(max(len(payload), 1)):
            try:
                self.client.table(self.table).insert(payload).execute()
                return
            except Exception as exc:  # noqa: BLE001
                missing = self._extract_missing_column(str(exc))
                if missing and missing in payload:
                    if self._try_add_column(missing, payload[missing]):
                        logger.info(
                            "Supabase auto-added missing column '%s' on table '%s'; retrying insert.",
                            missing,
                            self.table,
                        )
                        time.sleep(0.5)
                        continue
                    logger.warning(
                        "Supabase table '%s' missing column '%s'; could not auto-add, retrying without it.",
                        self.table,
                        missing,
                    )
                    payload.pop(missing, None)
                    continue
                logger.warning("Supabase insert failed: %s", exc)
                return

    @staticmethod
    def _extract_missing_column(error_text: str) -> Optional[str]:
        match = re.search(r"Could not find the '([^']+)' column", error_text)
        return match.group(1) if match else None

    def _try_add_column(self, column_name: str, sample_value: Any) -> bool:
        if not self.allow_dynamic_columns:
            return False
        if not self.db_password:
            logger.warning("SUPABASE_PASSWORD missing; cannot auto-add column '%s'.", column_name)
            return False

        normalized = self._normalize_identifier(column_name)
        if not normalized:
            logger.warning("Invalid dynamic column name '%s'.", column_name)
            return False

        sql_type = self._infer_sql_type(sample_value)
        conn_string = self._build_connection_string()
        if not conn_string:
            return False

        try:
            import psycopg
        except Exception as exc:  # noqa: BLE001
            logger.warning("psycopg is not available for dynamic schema evolution: %s", exc)
            return False

        try:
            with psycopg.connect(conn_string, connect_timeout=20) as conn:
                with conn.cursor() as cur:
                    query = (
                        f'ALTER TABLE IF EXISTS public."{self._normalize_identifier(self.table)}" '
                        f'ADD COLUMN IF NOT EXISTS "{normalized}" {sql_type};'
                    )
                    cur.execute(query)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dynamic column add failed for '%s': %s", normalized, exc)
            return False

    def _build_connection_string(self) -> Optional[str]:
        try:
            host = (urlparse(self.url).hostname or "").strip()
            if not host:
                return None
            project_ref = host.split(".")[0]
            db_host = f"db.{project_ref}.supabase.co"
            return (
                f"postgresql://postgres:{quote_plus(self.db_password or '')}"
                f"@{db_host}:5432/postgres?sslmode=require"
            )
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _normalize_identifier(name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized.lower()

    @staticmethod
    def _infer_sql_type(sample_value: Any) -> str:
        if isinstance(sample_value, bool):
            return "boolean"
        if isinstance(sample_value, int):
            return "bigint"
        if isinstance(sample_value, float):
            return "double precision"
        if isinstance(sample_value, (dict, list)):
            return "jsonb"
        return "text"
