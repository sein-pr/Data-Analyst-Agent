from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

from .logger import get_logger

logger = get_logger(__name__)


class QuickChartClient:
    def __init__(self, base_url: str = "https://quickchart.io/chart") -> None:
        self.base_url = base_url

    def render_chart(
        self,
        chart_config: Dict[str, Any],
        width: int,
        height: int,
        background: str = "transparent",
        version: str = "4",
        device_pixel_ratio: int = 2,
        fmt: str = "png",
    ) -> Optional[bytes]:
        payload = {
            "chart": chart_config,
            "width": width,
            "height": height,
            "backgroundColor": background,
            "devicePixelRatio": device_pixel_ratio,
            "format": fmt,
            "version": version,
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            if response.status_code >= 400:
                logger.warning("QuickChart error: %s", response.text)
                return None
            return response.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("QuickChart request failed: %s", exc)
            return None
