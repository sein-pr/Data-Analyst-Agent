from __future__ import annotations

from pathlib import Path

from .config import load_config
from .drive_client import DriveService
from .logger import get_logger

logger = get_logger(__name__)


def register_drive_webhook() -> None:
    config = load_config()
    if not (config.webhook_url and config.webhook_channel_id):
        raise RuntimeError("WEBHOOK_URL and WEBHOOK_CHANNEL_ID are required.")

    drive = DriveService(
        oauth_token_json=config.google_token_json,
        oauth_client_json_path=config.google_oauth_client_json_path,
        service_account_json_path=config.service_account_json_path,
    )
    page_token = drive.get_start_page_token()
    response = drive.watch_changes(
        page_token=page_token,
        webhook_url=config.webhook_url,
        channel_id=config.webhook_channel_id,
        token=config.webhook_token,
    )
    logger.info("Registered webhook channel: %s", response)

    token_path = Path(config.change_page_token_path or "state/drive_page_token.txt")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(page_token, encoding="utf-8")


if __name__ == "__main__":
    register_drive_webhook()
