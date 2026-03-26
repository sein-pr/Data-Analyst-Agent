from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Set

from .drive_client import DriveService
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessedRegistry:
    drive: DriveService
    folder_id: str
    filename: str = "processed_registry.json"

    def load(self) -> Set[str]:
        file = self.drive.find_file_by_name(self.folder_id, self.filename)
        if not file:
            return set()
        try:
            data = self.drive.download_file(file.id)
            payload = json.loads(data.decode("utf-8"))
            return set(payload.get("processed_ids", []))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to load processed registry; starting fresh.")
            return set()

    def save(self, processed_ids: Set[str]) -> None:
        payload = json.dumps({"processed_ids": sorted(processed_ids)}, indent=2).encode("utf-8")
        file = self.drive.find_file_by_name(self.folder_id, self.filename)
        if file:
            self.drive.update_file_content(file.id, payload, mime_type="application/json")
        else:
            self.drive.upload_file(self.folder_id, self.filename, payload, mime_type="application/json")

    def add(self, processed_ids: Set[str]) -> None:
        current = self.load()
        current.update(processed_ids)
        self.save(current)
