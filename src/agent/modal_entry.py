from __future__ import annotations

import modal

from .config import load_config
from .pipeline import AgentPipeline
from .webhook_app import app as webhook_app

app = modal.App("autonomous-data-analyst-agent")

ENV_SECRET_NAME = "data-agent-env"

image = modal.Image.debian_slim(python_version="3.11").pip_install_from_requirements(
    "requirements.txt"
)


@app.function(
    image=image,
    schedule=modal.Period(hours=4),
    secrets=[modal.Secret.from_name(ENV_SECRET_NAME)],
)
def run_agent() -> None:
    config = load_config()
    AgentPipeline(config).run()


@app.function(image=image, secrets=[modal.Secret.from_name(ENV_SECRET_NAME)])
@modal.asgi_app()
def webhook():
    return webhook_app
