from __future__ import annotations

from typing import Dict

from .utils import parse_output_spec, resolve_cell


def extract_outputs(workbook, default_sheet, outputs: Dict[str, object]) -> Dict[str, object]:
    results: Dict[str, object] = {}
    for name, spec in outputs.items():
        cell_ref, _ = parse_output_spec(spec)
        cell = resolve_cell(workbook, default_sheet, cell_ref)
        if cell is None:
            raise ValueError(f"Unable to resolve output cell '{cell_ref}'")
        results[name] = cell.value
    return results
