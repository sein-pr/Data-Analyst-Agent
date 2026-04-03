from __future__ import annotations

import sys
from pathlib import Path

import modal

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.config import load_config
from agent.pipeline import AgentPipeline
from agent.webhook_app import app as webhook_app

app = modal.App("autonomous-data-analyst-agent")

ENV_SECRET_NAME = "data-agent-env"
PYTHONPATH_ROOT = "/root/src"
SRS_ROOT = "/root/srs"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", remote_path=PYTHONPATH_ROOT, copy=True)
    .add_local_dir("srs", remote_path=SRS_ROOT, copy=True)
    .env({"PYTHONPATH": PYTHONPATH_ROOT})
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
