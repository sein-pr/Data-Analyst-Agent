from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request

from .config import load_config
from .webhook_sender import WebhookSender

from .logger import get_logger

logger = get_logger(__name__)

app = FastAPI()
LOG_PATH = Path("state/webhook_notifications.log")


@app.post("/drive/notify")
async def drive_notify(request: Request):
    headers = dict(request.headers)
    body = await request.body()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = f"Headers: {headers}\nBody: {body.decode('utf-8', errors='ignore')}\n\n"
    LOG_PATH.write_text(
        (LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else "") + entry,
        encoding="utf-8",
    )
    logger.info("Received Drive webhook notification.")
    sender = WebhookSender.from_config(load_config())
    sender.send(
        event="drive.change",
        payload={"headers": headers},
    )
    return {"status": "ok"}
