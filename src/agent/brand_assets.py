from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .drive_client import DriveService
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class BrandAssetPaths:
    guideline_path: Optional[Path]
    logo_full_path: Optional[Path]
    logo_symbol_path: Optional[Path]


def parse_drive_folder_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if "/" not in value:
        return value
    match = re.search(r"/folders/([^?]+)", value)
    if match:
        return match.group(1)
    return None


def fetch_brand_assets(
    drive: DriveService, folder_id: Optional[str], target_dir: Path
) -> BrandAssetPaths:
    target_dir.mkdir(parents=True, exist_ok=True)
    if not folder_id:
        logger.warning("No brand assets folder ID provided.")
        return BrandAssetPaths(None, None, None)

    guideline = _download_if_exists(drive, folder_id, "brand_guideline.md", target_dir)
    logo_full = _download_if_exists(drive, folder_id, "logo_large.png", target_dir)
    logo_symbol = _download_if_exists(drive, folder_id, "logo_small.png", target_dir)
    return BrandAssetPaths(guideline, logo_full, logo_symbol)


def _download_if_exists(
    drive: DriveService, folder_id: str, name: str, target_dir: Path
) -> Optional[Path]:
    file = drive.find_file_by_name(folder_id, name)
    if not file:
        return None
    content = drive.download_file(file.id)
    path = target_dir / name
    path.write_bytes(content)
    return path
