from __future__ import annotations

from typing import Dict, Tuple

from .utils import resolve_cell


def inject_inputs(workbook, default_sheet, inputs: Dict[str, object]) -> Dict[str, object]:
    inputs_used: Dict[str, object] = {}
    for target_ref, value in inputs.items():
        cell = resolve_cell(workbook, default_sheet, target_ref)
        if cell is None:
            raise ValueError(f"Unable to resolve input cell '{target_ref}'")
        cell.value = value
        inputs_used[cell.coordinate] = value
    return inputs_used
