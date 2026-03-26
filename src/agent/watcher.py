from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from .drive_client import DriveFile, DriveService
from .logger import get_logger

logger = get_logger(__name__)

STATE_PATH = Path("state/processed_files.json")


@dataclass
class WatchResult:
    new_files: List[DriveFile]
    processing_folder_id: str


def _load_processed_ids() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return set(data.get("processed_ids", []))


def _save_processed_ids(ids: Iterable[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"processed_ids": sorted(ids)}, indent=2),
        encoding="utf-8",
    )


def watch_folder(
    drive: DriveService,
    folder_id: str,
    extensions: Iterable[str] = (".xlsx", ".csv"),
    processed_ids: set[str] | None = None,
) -> WatchResult:
    if processed_ids is None:
        processed_ids = _load_processed_ids()
    extension_set = {ext.lower() for ext in extensions}
    files = drive.list_files(folder_id)
    new_files = [
        file
        for file in files
        if file.id not in processed_ids
        and Path(file.name).suffix.lower() in extension_set
    ]
    processing_folder_id = drive.find_or_create_subfolder(folder_id, "processing")
    logger.info("Found %s new files.", len(new_files))
    return WatchResult(new_files=new_files, processing_folder_id=processing_folder_id)


def mark_processed(file_ids: Iterable[str]) -> None:
    processed_ids = _load_processed_ids()
    processed_ids.update(file_ids)
    _save_processed_ids(processed_ids)
