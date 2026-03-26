from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from .analysis_engine import AnalysisEngine
from .brand import load_or_default_brand
from .brand_assets import fetch_brand_assets, parse_drive_folder_id
from .config import EnvConfig
from .data_healer import DataHealer
from .drive_client import DriveService
from .email_notifier import EmailNotifier
from .gemini_client import GeminiClient
from .insight_generator import InsightGenerator
from .logger import get_logger
from .pptx_generator import PPTXGenerator
from .processed_registry import ProcessedRegistry
from .watcher import mark_processed, watch_folder

logger = get_logger(__name__)


class AgentPipeline:
    def __init__(self, config: EnvConfig) -> None:
        self.config = config
        self.drive = DriveService(
            oauth_token_json=config.google_token_json,
            oauth_client_json_path=config.google_oauth_client_json_path,
            service_account_json_path=config.service_account_json_path,
        )
        self.llm_client = self._build_llm_client()
        self.healer = DataHealer(["Revenue", "Date", "Product Category"], llm_client=self.llm_client)
        self.analysis_engine = AnalysisEngine()
        self.insights = InsightGenerator(self.llm_client)
        self.emailer = EmailNotifier.from_config(config)
        self.page_token_path = Path(config.change_page_token_path or "state/drive_page_token.txt")

    def _build_llm_client(self) -> Optional[GeminiClient]:
        if not self.config.gemini_api_keys:
            logger.warning("No Gemini API keys found; using heuristic mapping only.")
            return None
        return GeminiClient(self.config.gemini_api_keys, self.config.gemini_model)

    def run(self) -> None:
        if not self.config.clean_data_drive_folder_id:
            raise RuntimeError("CLEAN_DATA_DRIVE_FOLDER_ID is not set.")
        if not self.config.reports_output_drive_folder_id:
            raise RuntimeError("REPORTS_OUTPUT_DRIVE_FOLDER_ID is not set.")

        self._refresh_change_page_token()

        registry = ProcessedRegistry(
            self.drive,
            self.config.reports_output_drive_folder_id,
            filename=self.config.processed_registry_filename or "processed_registry.json",
        )
        processed_ids = registry.load()
        watch_result = watch_folder(
            self.drive,
            self.config.clean_data_drive_folder_id,
            processed_ids=processed_ids,
        )
        processed_folder_id = self.drive.find_or_create_subfolder(
            self.config.clean_data_drive_folder_id, "processed"
        )
        failed_folder_id = self.drive.find_or_create_subfolder(
            self.config.clean_data_drive_folder_id, "failed"
        )

        if not watch_result.new_files:
            logger.info("No new files to process.")
            return

        for file in watch_result.new_files:
            logger.info("Processing file: %s", file.name)
            try:
                self._with_retries(lambda: self.drive.move_file(file.id, watch_result.processing_folder_id))
                data = self._with_retries(lambda: self.drive.download_file(file.id))
                df = self._load_dataframe(file.name, data)
                mapping = self.healer.map_columns(df.columns)
                df = df.rename(columns=mapping.mapping)
                if mapping.unmapped_required:
                    logger.error("Missing required columns: %s", mapping.unmapped_required)
                    self._upload_status(
                        filename=file.name,
                        message=f"Missing required columns: {', '.join(mapping.unmapped_required)}",
                    )
                    self._with_retries(lambda: self.drive.move_file(file.id, failed_folder_id))
                    self.emailer.send(
                        subject=f"Data Agent: Missing columns in {file.name}",
                        body=f"Missing required columns: {', '.join(mapping.unmapped_required)}",
                    )
                    continue
                analysis = self.analysis_engine.analyze(df)
                bullets = self.insights.generate_bullets(analysis)
                pptx_path = self._build_presentation(analysis, file.name, bullets, mapping)
                self._upload_report(pptx_path)
                self._write_processed_index(file.name, pptx_path.name, processed_folder_id)
                self._append_audit_log(file.name, pptx_path.name)
                self._with_retries(lambda: self.drive.move_file(file.id, processed_folder_id))
                logger.info("Generated report: %s", pptx_path)
                self.emailer.send(
                    subject=f"Data Agent: Report ready for {file.name}",
                    body=f"Report generated: {pptx_path.name}",
                )
                registry.add({file.id})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to process file %s", file.name)
                self._upload_status(
                    filename=file.name,
                    message=f"Processing failed: {exc}",
                )
                self._with_retries(lambda: self.drive.move_file(file.id, failed_folder_id))
                self.emailer.send(
                    subject=f"Data Agent: Failed to process {file.name}",
                    body=f"Error: {exc}",
                )
            finally:
                mark_processed([file.id])

    def _load_dataframe(self, filename: str, data: bytes) -> pd.DataFrame:
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(io.BytesIO(data))
        return pd.read_excel(io.BytesIO(data))

    def _build_presentation(self, analysis, filename: str, bullets, mapping) -> Path:
        assets = fetch_brand_assets(
            self.drive,
            parse_drive_folder_id(self.config.brand_assets_drive_folder_url),
            Path("state/brand_assets"),
        )
        brand = load_or_default_brand(assets.guideline_path)
        generator = PPTXGenerator(
            brand,
            logo_full_path=assets.logo_full_path,
            logo_symbol_path=assets.logo_symbol_path,
        )
        output_name = f"{Path(filename).stem}_report.pptx"
        output_path = Path("output") / output_name
        return generator.build(
            analysis,
            output_path,
            bullets,
            mapping,
            report_source=filename,
            primary_font=self.config.brand_font_primary,
        )

    def _upload_report(self, pptx_path: Path) -> None:
        content = pptx_path.read_bytes()
        self.drive.upload_file(
            self.config.reports_output_drive_folder_id,
            pptx_path.name,
            content,
        )

    def _upload_status(self, filename: str, message: str) -> None:
        status_name = f"{Path(filename).stem}_status.txt"
        content = message.encode("utf-8")
        self.drive.upload_file(
            self.config.reports_output_drive_folder_id,
            status_name,
            content,
            mime_type="text/plain",
        )

    def _with_retries(self, fn, attempts: int = 3, delay_seconds: int = 2):
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("Retry %s/%s failed: %s", attempt, attempts, exc)
                time.sleep(delay_seconds * attempt)
        if last_exc:
            raise last_exc
        raise RuntimeError("Retry helper failed with unknown error.")

    def _write_processed_index(self, source_name: str, report_name: str, folder_id: str) -> None:
        content = f"Source: {source_name}\nReport: {report_name}\n"
        self.drive.upload_file(
            folder_id,
            f"{Path(source_name).stem}_processed.txt",
            content.encode("utf-8"),
            mime_type="text/plain",
        )

    def _append_audit_log(self, source_name: str, report_name: str) -> None:
        log_name = "processed_audit_log.csv"
        header = "timestamp,source_file,report_file\n"
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},{source_name},{report_name}\n"
        existing = self.drive.find_file_by_name(self.config.reports_output_drive_folder_id, log_name)
        if existing:
            current = self.drive.download_file(existing.id).decode("utf-8")
            updated = current + line
            self.drive.update_file_content(existing.id, updated.encode("utf-8"), mime_type="text/csv")
        else:
            self.drive.upload_file(
                self.config.reports_output_drive_folder_id,
                log_name,
                (header + line).encode("utf-8"),
                mime_type="text/csv",
            )

    def _refresh_change_page_token(self) -> None:
        try:
            token = self.drive.get_start_page_token()
            self.page_token_path.parent.mkdir(parents=True, exist_ok=True)
            self.page_token_path.write_text(token, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to refresh Drive page token: %s", exc)
