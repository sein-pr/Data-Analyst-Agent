from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _get_env_json(name: str) -> Optional[Dict[str, Any]]:
    raw = os.getenv(name)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _get_env_list(prefix: str, max_items: int = 10) -> List[str]:
    values: List[str] = []
    for i in range(1, max_items + 1):
        value = os.getenv(f"{prefix}{i}")
        if value:
            values.append(value)
    return values


@dataclass(frozen=True)
class EnvConfig:
    gemini_api_keys: List[str]
    gemini_model: str

    modal_token_id: Optional[str]
    modal_token_secret: Optional[str]

    google_oauth_client_json_path: Optional[str]
    google_token_json: Optional[Dict[str, Any]]
    service_account_json_path: Optional[str]

    clean_data_drive_folder_id: Optional[str]
    reports_output_drive_folder_id: Optional[str]
    brand_assets_drive_folder_url: Optional[str]

    mail_server: Optional[str]
    mail_port: Optional[int]
    mail_use_tls: Optional[bool]
    mail_username: Optional[str]
    mail_password: Optional[str]
    mail_default_sender: Optional[str]
    notify_email_to: Optional[str]


def load_config() -> EnvConfig:
    mail_port = os.getenv("MAIL_PORT")
    mail_use_tls = os.getenv("MAIL_USE_TLS")
    return EnvConfig(
        gemini_api_keys=_get_env_list("GEMINI_API_KEY_"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        modal_token_id=os.getenv("MODAL_TOKEN_ID"),
        modal_token_secret=os.getenv("MODAL_TOKEN_SECRET"),
        google_oauth_client_json_path=os.getenv("GOOGLE_OAUTH_CLIENT_JSON_PATH"),
        google_token_json=_get_env_json("GOOGLE_TOKEN_JSON"),
        service_account_json_path=os.getenv("SERVICE_ACCOUNT_JSON_PATH"),
        clean_data_drive_folder_id=os.getenv("CLEAN_DATA_DRIVE_FOLDER_ID"),
        reports_output_drive_folder_id=os.getenv("REPORTS_OUTPUT_DRIVE_FOLDER_ID"),
        brand_assets_drive_folder_url=os.getenv("BRAND_ASSETS_DRIVE_FOLDER_URL"),
        mail_server=os.getenv("MAIL_SERVER"),
        mail_port=int(mail_port) if mail_port else None,
        mail_use_tls=mail_use_tls.lower() == "true" if mail_use_tls else None,
        mail_username=os.getenv("MAIL_USERNAME"),
        mail_password=os.getenv("MAIL_PASSWORD"),
        mail_default_sender=os.getenv("MAIL_DEFAULT_SENDER"),
        notify_email_to=os.getenv("NOTIFY_EMAIL_TO"),
    )
