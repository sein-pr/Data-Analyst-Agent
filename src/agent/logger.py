from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path

_CONFIGURED = False
_RUN_LOG_PATH: Path | None = None


def _configure_root_logger() -> None:
    global _CONFIGURED, _RUN_LOG_PATH
    if _CONFIGURED:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    run_dir = Path("runs")
    run_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _RUN_LOG_PATH = run_dir / f"run{timestamp}.txt"
    file_handler = logging.FileHandler(_RUN_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_run_log_path() -> Path | None:
    return _RUN_LOG_PATH

def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    return logging.getLogger(name)
