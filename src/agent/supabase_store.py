from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set
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
        self._overflow_columns: Set[str] = set()
        self._overflow_table_ready: bool = False
        self._dynamic_add_blocked_until = 0.0

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
            if not data:
                return None
            latest = data[0]
            analysis_id = latest.get("id")
            if analysis_id is not None:
                dynamic = self._fetch_dynamic_fields(analysis_id)
                if dynamic:
                    latest["dynamic_fields"] = dynamic
                    latest.update(dynamic)
            return latest
        except Exception as exc:  # noqa: BLE001
            logger.warning("Supabase fetch failed: %s", exc)
            return None

    def insert(self, record: Dict[str, Any]) -> None:
        payload = dict(record)
        dynamic_payload: Dict[str, Any] = {}
        for column in list(record.keys()):
            normalized = self._normalize_identifier(column)
            if normalized in self._overflow_columns and column in payload:
                dynamic_payload[column] = payload[column]
                payload.pop(column, None)

        for _ in range(max(len(record) + 2, 3)):
            try:
                response = self.client.table(self.table).insert(payload).execute()
                inserted_rows = response.data or []
                inserted = inserted_rows[0] if inserted_rows else {}
                if dynamic_payload:
                    self._persist_dynamic_fields(inserted, dynamic_payload)
                return
            except Exception as exc:  # noqa: BLE001
                missing = self._extract_missing_column(str(exc))
                if missing and missing in payload:
                    normalized_missing = self._normalize_identifier(missing)
                    if (
                        normalized_missing not in self._overflow_columns
                        and self._try_add_column(missing, payload[missing])
                    ):
                        logger.info(
                            "Supabase auto-added missing column '%s' on table '%s'; retrying insert.",
                            missing,
                            self.table,
                        )
                        time.sleep(0.5)
                        continue
                    self._overflow_columns.add(normalized_missing)
                    dynamic_payload[missing] = payload.pop(missing, None)
                    logger.info(
                        "Storing dynamic field '%s' in sidecar table for '%s'.",
                        missing,
                        self.table,
                    )
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
        if time.time() < self._dynamic_add_blocked_until:
            return False
        if not self.db_password:
            logger.warning("SUPABASE_PASSWORD missing; cannot auto-add column '%s'.", column_name)
            self._dynamic_add_blocked_until = time.time() + 1800
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
            self._dynamic_add_blocked_until = time.time() + 1800
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
            text = str(exc).lower()
            if "failed to resolve host" in text or "getaddrinfo failed" in text:
                self._dynamic_add_blocked_until = time.time() + 1800
                logger.info(
                    "Dynamic column add paused for 30 minutes due to DNS/connectivity issue on Supabase DB host."
                )
                return False
            logger.warning("Dynamic column add failed for '%s': %s", normalized, exc)
            return False

    def _persist_dynamic_fields(self, inserted_row: Dict[str, Any], dynamic_payload: Dict[str, Any]) -> None:
        analysis_id = inserted_row.get("id")
        if analysis_id is None:
            logger.warning("Inserted row has no 'id'; cannot persist dynamic fields.")
            return
        if not dynamic_payload:
            return
        if not self._ensure_dynamic_table():
            logger.info("Dynamic sidecar table unavailable; skipping dynamic field persistence.")
            return
        rows = [
            {
                "analysis_id": analysis_id,
                "field_name": self._normalize_identifier(name),
                "field_value_text": self._serialize_dynamic_value(value),
            }
            for name, value in dynamic_payload.items()
        ]
        try:
            self.client.table(self._dynamic_table_name()).insert(rows).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist dynamic fields in sidecar table: %s", exc)

    def _fetch_dynamic_fields(self, analysis_id: Any) -> Dict[str, Any]:
        if analysis_id is None:
            return {}
        if not self._ensure_dynamic_table():
            return {}
        try:
            response = (
                self.client.table(self._dynamic_table_name())
                .select("field_name,field_value_text")
                .eq("analysis_id", analysis_id)
                .execute()
            )
            data = response.data or []
            dynamic: Dict[str, Any] = {}
            for row in data:
                name = str(row.get("field_name", "")).strip()
                if not name:
                    continue
                dynamic[name] = self._deserialize_dynamic_value(row.get("field_value_text"))
            return dynamic
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load dynamic fields from sidecar table: %s", exc)
            return {}

    def _ensure_dynamic_table(self) -> bool:
        if self._overflow_table_ready:
            return True
        if time.time() < self._dynamic_add_blocked_until:
            return False
        table_name = self._dynamic_table_name()
        try:
            self.client.table(table_name).select("id").limit(1).execute()
            self._overflow_table_ready = True
            return True
        except Exception as exc:  # noqa: BLE001
            if not self._is_missing_table_error(str(exc)):
                logger.warning("Dynamic sidecar table probe failed: %s", exc)
                self._dynamic_add_blocked_until = time.time() + 300
                return False
        conn_string = self._build_connection_string()
        if not conn_string:
            return False
        if time.time() < self._dynamic_add_blocked_until:
            return False
        try:
            import psycopg
        except Exception as exc:  # noqa: BLE001
            logger.warning("psycopg is not available for dynamic sidecar creation: %s", exc)
            self._dynamic_add_blocked_until = time.time() + 1800
            return False
        base_table = self._normalize_identifier(self.table)
        dynamic_table = self._normalize_identifier(table_name)
        try:
            with psycopg.connect(conn_string, connect_timeout=20) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f'''
                        CREATE TABLE IF NOT EXISTS public."{dynamic_table}" (
                            id bigserial PRIMARY KEY,
                            analysis_id bigint NOT NULL REFERENCES public."{base_table}"(id) ON DELETE CASCADE,
                            field_name text NOT NULL,
                            field_value_text text NULL,
                            created_at timestamptz NOT NULL DEFAULT now(),
                            UNIQUE (analysis_id, field_name)
                        );
                        '''
                    )
            self._overflow_table_ready = True
            logger.info("Ensured dynamic sidecar table exists: %s", dynamic_table)
            return True
        except Exception as exc:  # noqa: BLE001
            text = str(exc).lower()
            if "failed to resolve host" in text or "getaddrinfo failed" in text:
                self._dynamic_add_blocked_until = time.time() + 1800
                logger.info(
                    "Dynamic sidecar creation paused for 30 minutes due to DNS/connectivity issue on Supabase DB host."
                )
                return False
            logger.warning("Failed to create dynamic sidecar table '%s': %s", dynamic_table, exc)
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

    def _dynamic_table_name(self) -> str:
        return f"{self._normalize_identifier(self.table)}_dynamic_fields"

    @staticmethod
    def _is_missing_table_error(error_text: str) -> bool:
        text = (error_text or "").lower()
        return (
            ("relation" in text and "does not exist" in text)
            or "could not find the table" in text
            or "pgrst205" in text
        )

    @staticmethod
    def _serialize_dynamic_value(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return str(value)

    @staticmethod
    def _deserialize_dynamic_value(value: Any) -> Any:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return ""
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            return text
