from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .extractor import extract_outputs
from .injector import inject_inputs
from .loader import load_model
from .utils import find_cell_refs, parse_output_spec, resolve_cell
from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExcelModelConfig:
    model_path: str
    sheet: Optional[str]
    inputs: Dict[str, object]
    outputs: Dict[str, object]
    engine: str = "auto"


class ExcelModelRunner:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def load_config(self, department: str) -> Optional[ExcelModelConfig]:
        config_path = self.config_dir / f"{department}.json"
        if not config_path.exists():
            fallback = self.config_dir / "default.json"
            if not fallback.exists():
                return None
            config_path = fallback
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        return ExcelModelConfig(
            model_path=str(raw.get("model_path", "")),
            sheet=raw.get("sheet"),
            inputs=raw.get("inputs", {}),
            outputs=raw.get("outputs", {}),
            engine=raw.get("engine", "auto"),
        )

    def run_for_department(
        self, department: str, context: Dict[str, Dict[str, object]]
    ) -> Optional[Dict[str, object]]:
        config = self.load_config(department)
        if not config:
            return None
        resolved_inputs = resolve_inputs(config.inputs, context)
        return run_excel_model(
            model_path=config.model_path,
            inputs=resolved_inputs,
            outputs=config.outputs,
            sheet=config.sheet,
            engine=config.engine,
        )


def run_excel_model(
    model_path: str,
    inputs: Dict[str, object],
    outputs: Dict[str, object],
    sheet: Optional[str] = None,
    engine: str = "auto",
) -> Dict[str, object]:
    result = {
        "status": "error",
        "model_name": Path(model_path).name if model_path else "",
        "inputs_used": {},
        "outputs": {},
        "insights_ready": False,
        "errors": [],
    }

    try:
        model = load_model(model_path, sheet_name=sheet)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"load_error: {exc}")
        return result

    try:
        inputs_used = inject_inputs(model.workbook, model.sheet, inputs)
        result["inputs_used"] = inputs_used
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"input_error: {exc}")
        return result

    outputs_result: Dict[str, object] = {}
    try:
        if engine in ("auto", "efc"):
            outputs_result = _evaluate_with_efc(model, outputs)
        if not outputs_result:
            outputs_result = extract_outputs(model.workbook, model.sheet, outputs)
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"output_error: {exc}")

    # Formula fallback for any missing outputs
    for name, spec in outputs.items():
        if name in outputs_result and outputs_result[name] not in (None, ""):
            continue
        _, formula = parse_output_spec(spec)
        if formula:
            try:
                outputs_result[name] = evaluate_formula_expression(
                    model.workbook, model.sheet, formula
                )
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(f"formula_error:{name}:{exc}")

    result["outputs"] = outputs_result
    result["status"] = "success" if outputs_result else "partial"
    result["insights_ready"] = bool(outputs_result)
    return result


def _evaluate_with_efc(model, outputs: Dict[str, object]) -> Dict[str, object]:
    try:
        from efc.interfaces.iopenpyxl import OpenpyxlInterface
    except Exception:  # noqa: BLE001
        return {}

    interface = OpenpyxlInterface(model.workbook, use_cache=False)
    results: Dict[str, object] = {}
    for name, spec in outputs.items():
        cell_ref, _ = parse_output_spec(spec)
        if "!" in cell_ref:
            sheet_name, cell = cell_ref.split("!", 1)
        else:
            sheet_name = model.sheet.title
            cell = cell_ref
        try:
            results[name] = interface.calc_cell(cell, sheet_name)
        except Exception:  # noqa: BLE001
            continue
    return results


def resolve_inputs(inputs: Dict[str, object], context: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    resolved: Dict[str, object] = {}
    for cell_ref, value in inputs.items():
        if isinstance(value, str) and ":" in value:
            prefix, key = value.split(":", 1)
            lookup = context.get(prefix.strip(), {})
            resolved[cell_ref] = lookup.get(key.strip())
        else:
            resolved[cell_ref] = value
    return resolved


def evaluate_formula_expression(workbook, sheet, expression: str):
    refs = find_cell_refs(expression)
    values: Dict[str, object] = {}
    for ref in refs:
        cell = resolve_cell(workbook, sheet, ref)
        values[ref] = cell.value if cell else None
    tree = ast.parse(expression, mode="eval")
    return _safe_eval(tree.body, values)


def _safe_eval(node, values: Dict[str, object]):
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left, values)
        right = _safe_eval(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError("Unsupported operator")
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval(node.operand, values)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("Unsupported unary operator")
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError("Unsupported expression")
