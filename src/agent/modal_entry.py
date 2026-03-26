from __future__ import annotations

import modal

from .config import load_config
from .pipeline import AgentPipeline

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
    )
)


@app.function(image=image, schedule=modal.Period(hours=4))
def run_agent() -> None:
    config = load_config()
    AgentPipeline(config).run()
