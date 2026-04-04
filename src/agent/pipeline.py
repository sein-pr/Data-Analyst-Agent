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
from .groq_client import GroqClient
from .llm_router import LLMRouter
from .insight_generator import InsightGenerator
from .logger import get_logger
from .pptx_generator import PPTXGenerator
from .processed_registry import ProcessedRegistry
from .watcher import mark_processed, watch_folder
from .department_detector import detect_departments
from .prompt_loader import PromptLoader
from .supabase_store import SupabaseStore
from .excel_model.runner import ExcelModelRunner
from .excel_model.kpi_selector import select_kpis
from .excel_model.visual_planner import plan_visuals

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
        self.prompt_loader = PromptLoader()
        self.excel_models = ExcelModelRunner(Path(config.excel_model_config_dir or "srs/excel_models"))
        self.supabase = None
        if config.supabase_url and config.supabase_key:
            self.supabase = SupabaseStore(
                config.supabase_url,
                config.supabase_key,
                table=config.supabase_table or "analysis_history",
            )
        self.emailer = EmailNotifier.from_config(config)
        self.page_token_path = Path(config.change_page_token_path or "state/drive_page_token.txt")

    def _build_llm_client(self) -> Optional[GeminiClient]:
        clients = []
        if self.config.gemini_api_keys:
            clients.append(GeminiClient(self.config.gemini_api_keys, self.config.gemini_model))
        if self.config.groq_api_keys:
            clients.append(GroqClient(self.config.groq_api_keys, self.config.groq_model))
        if not clients:
            logger.warning("No LLM API keys found; using heuristic mapping only.")
            return None
        return LLMRouter(clients)

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

        if not watch_result.new_files and self.config.retry_failed_on_empty:
            failed_candidates = self.drive.list_files(failed_folder_id)
            retry_files = [
                file
                for file in failed_candidates
                if Path(file.name).suffix.lower() in {".xlsx", ".csv"}
            ]
            if retry_files:
                logger.info("No new files in root; retrying from failed folder.")
                watch_result = watch_result.__class__(
                    new_files=[retry_files[0]],
                    processing_folder_id=watch_result.processing_folder_id,
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
                departments = detect_departments(df.columns.tolist())
                if not departments:
                    logger.warning("No department match found; skipping report generation.")
                    self._with_retries(lambda: self.drive.move_file(file.id, processed_folder_id))
                    continue

                previous = None
                if self.supabase:
                    previous = self.supabase.fetch_latest(analysis.schema_signature)

                excel_result = None
                if departments:
                    context = {
                        "kpi": analysis.kpis,
                        "summary": analysis.summary,
                        "data_quality": analysis.data_quality,
                        "schema": analysis.schema_overview,
                        "top_products": analysis.top_products,
                        "monthly_revenue": analysis.monthly_revenue,
                        "revenue_by_channel": analysis.revenue_by_channel,
                        "revenue_by_region": analysis.revenue_by_region,
                        "outliers": analysis.outliers,
                        "supabase": previous or {},
                    }
                    excel_result = self.excel_models.run_for_department(
                        departments[0].name,
                        context,
                        departments=[d.name for d in departments],
                        dataset_name=Path(file.name).stem,
                        llm_client=self.llm_client,
                    )

                for dept in departments:
                    context = {
                        "kpi": analysis.kpis,
                        "summary": analysis.summary,
                        "data_quality": analysis.data_quality,
                        "schema": analysis.schema_overview,
                        "top_products": analysis.top_products,
                        "monthly_revenue": analysis.monthly_revenue,
                        "revenue_by_channel": analysis.revenue_by_channel,
                        "revenue_by_region": analysis.revenue_by_region,
                    }
                    context["supabase"] = previous or {}
                    dept_prompt = self.prompt_loader.load_department_prompt(dept.name)
                    pp_prompt = self.prompt_loader.load_powerpoint_prompt()
                    prompt = (
                        f"{pp_prompt}\n\n"
                        "You are a JSON generator.\n\n"
                        "Your task is to return ONLY valid JSON.\n\n"
                        "STRICT RULES:\n"
                        "- Output ONLY JSON\n"
                        "- Do NOT include explanations\n"
                        "- Do NOT include markdown (no ```json)\n"
                        "- Do NOT include text before or after\n"
                        "- Do NOT include comments\n"
                        "- Ensure the JSON is valid and parsable\n\n"
                        "If you violate these rules, the output is invalid.\n\n"
                        "JSON SCHEMA:\n"
                        "{\n"
                        "  \"title\": \"string\",\n"
                        "  \"executive_summary\": [\"string\"],\n"
                        "  \"objectives\": [\"string\"],\n"
                        "  \"data_overview\": [\"string\"],\n"
                        "  \"methodology\": [\"string\"],\n"
                        "  \"key_findings\": [\"string\"],\n"
                        "  \"insights_interpretation\": [\"string\"],\n"
                        "  \"department_analysis\": [\"string\"],\n"
                        "  \"comparative_analysis\": [\"string\"],\n"
                        "  \"risks_limitations\": [\"string\"],\n"
                        "  \"recommendations\": [\"string\"],\n"
                        "  \"conclusion\": [\"string\"],\n"
                        "  \"next_steps\": [\"string\"],\n"
                        "  \"appendix\": [\"string\"]\n"
                        "}\n\n"
                        "Every field must be present. If data is not available, write \"Not applicable\" in the list.\n\n"
                        "Now generate the JSON based on the input data.\n\n"
                        "Dataset is provided below; do not ask for it.\n\n"
                        f"{dept_prompt or ''}\n\n"
                        "Use the following data summaries:\n"
                        f"KPI Summary: {analysis.kpis}\n"
                        f"Top Products: {analysis.top_products}\n"
                        f"Outliers: {analysis.outliers}\n"
                        f"Data Quality: {analysis.data_quality}\n"
                        f"Schema: {analysis.schema_overview}\n"
                        f"Excel Model Result: {excel_result or {}}\n"
                        f"Previous Analysis: {previous or {}}\n"
                    )
                    sections = self.insights.generate_sections(
                        analysis,
                        prompt_override=prompt,
                        previous_analysis=previous,
                    )
                    selected_kpis = select_kpis(analysis.kpis, llm_client=self.llm_client, limit=6, department=dept.name)
                    selected_visuals = plan_visuals(
                        {
                            "monthly_revenue": analysis.monthly_revenue,
                            "top_products": analysis.top_products,
                            "revenue_by_channel": analysis.revenue_by_channel,
                            "revenue_by_region": analysis.revenue_by_region,
                        },
                        llm_client=self.llm_client,
                    )
                    pptx_path = self._build_presentation(
                        analysis,
                        f"{dept.name}_{file.name}",
                        sections,
                        mapping,
                        department=dept.name,
                        previous_analysis=previous,
                        selected_kpis=selected_kpis,
                        selected_visuals=selected_visuals,
                    )
                    self._upload_report(pptx_path)
                    if excel_result and excel_result.get("dashboard_path"):
                        dashboard_path = Path(excel_result["dashboard_path"])
                        if dashboard_path.exists():
                            self._upload_report(dashboard_path)
                    self._write_processed_index(file.name, pptx_path.name, processed_folder_id)
                    self._append_audit_log(file.name, pptx_path.name)
                    logger.info("Generated report: %s", pptx_path)

                if self.supabase:
                    self.supabase.insert(
                        {
                            "dataset_name": file.name,
                            "schema_signature": analysis.schema_signature,
                            "kpis": analysis.kpis,
                            "top_products": analysis.top_products,
                            "outliers": analysis.outliers,
                        }
                    )
                self._with_retries(lambda: self.drive.move_file(file.id, processed_folder_id))
                self.emailer.send(
                    subject=f"Data Agent: Report ready for {file.name}",
                    body=f"Report(s) generated for departments: {', '.join([d.name for d in departments])}",
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

    def _build_presentation(
        self,
        analysis,
        filename: str,
        sections: dict,
        mapping,
        department: str,
        previous_analysis: dict | None = None,
        selected_kpis: list | None = None,
        selected_visuals: list | None = None,
    ) -> Path:
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
        output_name = f"{Path(filename).stem}_{department}_report.pptx"
        output_path = Path("output") / output_name
        return generator.build(
            analysis,
            output_path,
            sections,
            mapping,
            report_source=filename,
            primary_font=self.config.brand_font_primary,
            department_label=department,
            previous_analysis=previous_analysis,
            selected_kpis=selected_kpis,
            selected_visuals=selected_visuals,
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
