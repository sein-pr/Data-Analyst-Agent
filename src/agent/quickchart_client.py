from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, Optional

import requests

from .logger import get_logger

logger = get_logger(__name__)


class QuickChartClient:
    def __init__(self, base_url: str = "https://quickchart.io/chart") -> None:
        self.base_url = base_url
        self.max_attempts = 4
        self.timeout = (20, 60)

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
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = requests.post(self.base_url, json=payload, timeout=self.timeout)
                if response.status_code >= 400:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_attempts:
                        delay = self._backoff_delay(attempt)
                        logger.warning(
                            "QuickChart HTTP %s (attempt %s/%s). Retrying in %.1fs.",
                            response.status_code,
                            attempt,
                            self.max_attempts,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    logger.warning("QuickChart error: %s", response.text)
                    return None
                return response.content
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.max_attempts and self._is_transient_error(exc):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "QuickChart transient failure (attempt %s/%s). Retrying in %.1fs: %s",
                        attempt,
                        self.max_attempts,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    continue
                logger.warning("QuickChart request failed: %s", exc)
                return None
        if last_exc:
            logger.warning("QuickChart failed after retries: %s", last_exc)
        return None

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            token in text
            for token in [
                "timeout",
                "timed out",
                "connection reset",
                "temporarily unavailable",
                "500",
                "502",
                "503",
                "504",
            ]
        )

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        return min(12.0, float(2 ** attempt)) + random.uniform(0.0, 0.4)
