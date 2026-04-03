from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

CELL_REF_RE = re.compile(r"^[A-Za-z]{1,3}[0-9]{1,7}$")
SHEET_REF_RE = re.compile(r"^([^!]+)!([A-Za-z]{1,3}[0-9]{1,7})$")


def resolve_cell(workbook, default_sheet, ref: str):
    if not ref:
        return None
    ref = ref.strip()

    sheet = default_sheet
    cell_ref = ref

    match = SHEET_REF_RE.match(ref)
    if match:
        sheet_name, cell_ref = match.group(1), match.group(2)
        if sheet_name not in workbook.sheetnames:
            raise ValueError(f"Sheet '{sheet_name}' not found for ref '{ref}'")
        sheet = workbook[sheet_name]

    if CELL_REF_RE.match(cell_ref):
        return sheet[cell_ref]

    # Named range support
    defined_name = workbook.defined_names.get(cell_ref)
    if defined_name is None:
        return None
    destinations = list(defined_name.destinations)
    if not destinations:
        return None
    dest_sheet_name, dest_range = destinations[0]
    if dest_sheet_name not in workbook.sheetnames:
        return None
    dest_sheet = workbook[dest_sheet_name]
    # For ranges, take the top-left cell
    if ":" in dest_range:
        start = dest_range.split(":", 1)[0]
        return dest_sheet[start]
    return dest_sheet[dest_range]


def parse_output_spec(spec) -> Tuple[str, Optional[str]]:
    if isinstance(spec, dict):
        cell = spec.get("cell") or ""
        formula = spec.get("formula")
        return str(cell), str(formula) if formula else None
    return str(spec), None


def find_cell_refs(expression: str) -> Iterable[str]:
    if not expression:
        return []
    return set(re.findall(r"\\b[A-Za-z]{1,3}[0-9]{1,7}\\b", expression))
