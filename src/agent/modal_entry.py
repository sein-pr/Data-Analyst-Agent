from __future__ import annotations

import modal

from .config import load_config
from .pipeline import AgentPipeline
from .webhook_app import app as webhook_app

app = modal.App("autonomous-data-analyst-agent")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "pandas",
        "openpyxl",
        "python-pptx",
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib",
        "google-generativeai",
        "fastapi",
        "uvicorn",
    )
)


@app.function(image=image, schedule=modal.Period(hours=4))
def run_agent() -> None:
    config = load_config()
    AgentPipeline(config).run()


@app.function(image=image)
@modal.asgi_app()
def webhook():
    return webhook_app
