from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import pandas as pd

from .analysis_engine import AnalysisEngine
from .brand import load_brand_guidelines
from .config import EnvConfig
from .data_healer import DataHealer
from .drive_client import DriveService
from .gemini_client import GeminiClient
from .insight_generator import InsightGenerator
from .logger import get_logger
from .pptx_generator import PPTXGenerator
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

    def _build_llm_client(self) -> Optional[GeminiClient]:
        if not self.config.gemini_api_keys:
            logger.warning("No Gemini API keys found; using heuristic mapping only.")
            return None
        return GeminiClient(self.config.gemini_api_keys[0], self.config.gemini_model)

    def run(self) -> None:
        if not self.config.clean_data_drive_folder_id:
            raise RuntimeError("CLEAN_DATA_DRIVE_FOLDER_ID is not set.")
        if not self.config.reports_output_drive_folder_id:
            raise RuntimeError("REPORTS_OUTPUT_DRIVE_FOLDER_ID is not set.")

        watch_result = watch_folder(self.drive, self.config.clean_data_drive_folder_id)

        if not watch_result.new_files:
            logger.info("No new files to process.")
            return

        for file in watch_result.new_files:
            logger.info("Processing file: %s", file.name)
            try:
                self.drive.move_file(file.id, watch_result.processing_folder_id)
                data = self.drive.download_file(file.id)
                df = self._load_dataframe(file.name, data)
                mapping = self.healer.map_columns(df.columns)
                df = df.rename(columns=mapping.mapping)
                if mapping.unmapped_required:
                    logger.error("Missing required columns: %s", mapping.unmapped_required)
                    self._upload_status(
                        filename=file.name,
                        message=f"Missing required columns: {', '.join(mapping.unmapped_required)}",
                    )
                    continue
                analysis = self.analysis_engine.analyze(df)
                bullets = self.insights.generate_bullets(analysis)
                pptx_path = self._build_presentation(analysis, file.name, bullets, mapping)
                self._upload_report(pptx_path)
                logger.info("Generated report: %s", pptx_path)
            finally:
                mark_processed([file.id])

    def _load_dataframe(self, filename: str, data: bytes) -> pd.DataFrame:
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(io.BytesIO(data))
        return pd.read_excel(io.BytesIO(data))

    def _build_presentation(self, analysis, filename: str, bullets, mapping) -> Path:
        brand_path = Path("srs/brand_guideline.md")
        brand = load_brand_guidelines(brand_path)
        if not brand:
            raise RuntimeError("Brand guidelines missing; cannot render PPTX.")
        generator = PPTXGenerator(brand)
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
