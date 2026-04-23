from __future__ import annotations

from pathlib import Path
from typing import List, Optional


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

    def available_departments(self) -> List[str]:
        departments: List[str] = []
        if (self.base_dir / "executive.md").exists():
            departments.append("executive")
        for path in sorted(self.base_dir.glob("*_department.md")):
            name = path.stem.replace("_department", "").strip().lower()
            if name and name not in departments:
                departments.append(name)
        if not departments:
            departments = ["executive"]
        return departments

    def _read(self, name: str) -> str:
        path = self.base_dir / name
        return path.read_text(encoding="utf-8", errors="replace")
