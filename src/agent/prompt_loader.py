from __future__ import annotations

from pathlib import Path
from typing import Optional


class PromptLoader:
    def __init__(self, base_dir: Path = Path("srs/prompts")) -> None:
        self.base_dir = base_dir

    def load_powerpoint_prompt(self) -> str:
        return self._read("powerpoint_prompt.md")

    def load_department_prompt(self, department: str) -> Optional[str]:
        filename = f"{department}_department.md" if department != "executive" else "executive.md"
        path = self.base_dir / filename
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="replace")

    def _read(self, name: str) -> str:
        path = self.base_dir / name
        return path.read_text(encoding="utf-8", errors="replace")
