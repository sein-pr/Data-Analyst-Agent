from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class BrandPalette:
    primary: str
    secondary: str
    neutral: str


@dataclass
class BrandGuidelines:
    name: str
    tagline: Optional[str]
    palette: BrandPalette


def load_brand_guidelines(path: Path) -> Optional[BrandGuidelines]:
    if not path.exists():
        logger.warning("Brand guideline file not found at %s.", path)
        return None
    text = path.read_text(encoding="utf-8")
    name_match = re.search(r"#\s+(.+?)\s+–\s+Brand Guidelines", text)
    name = name_match.group(1).strip() if name_match else "Brand"
    tagline_match = re.search(r"\*([^\n]+)\*", text)
    tagline = tagline_match.group(1).strip() if tagline_match else None

    colors = re.findall(r"`(#[0-9A-Fa-f]{6})`", text)
    if len(colors) < 3:
        logger.warning("Could not parse full color palette; using defaults.")
        colors = ["#006D77", "#83C5BE", "#EDF6F9"]

    return BrandGuidelines(
        name=name,
        tagline=tagline,
        palette=BrandPalette(primary=colors[0], secondary=colors[1], neutral=colors[2]),
    )


def load_or_default_brand(path: Optional[Path]) -> BrandGuidelines:
    if path:
        guidelines = load_brand_guidelines(path)
        if guidelines:
            return guidelines
    logger.warning("Using default brand guidelines.")
    return BrandGuidelines(
        name="Brand",
        tagline="Automated Insights",
        palette=BrandPalette(primary="#006D77", secondary="#83C5BE", neutral="#EDF6F9"),
    )
