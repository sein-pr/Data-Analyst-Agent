# Excel Model Configuration

Place department-specific JSON configs here. The agent will look for:

- srs/excel_models/<department>.json
- srs/excel_models/default.json (fallback)

## Example (finance.json)

{
  "model_path": "srs/excel_models/finance_model.xlsx",
  "sheet": "Model",
  "engine": "auto",
  "inputs": {
    "B2": "kpi:Total Revenue",
    "B3": "kpi:Total Cost",
    "B4": "kpi:MoM Growth"
  },
  "outputs": {
    "profit": "B10",
    "forecast": {"cell": "B11", "formula": "B2-B3"}
  }
}

## Input Resolution

The runner resolves values using prefixes:

- kpi:        analysis KPIs
- summary:    analysis summary
- data_quality: data quality metrics
- schema:     schema overview

## Output Evaluation

- engine=auto will try excel-formulas-calculator (efc) if installed
- if a formula is provided in an output, the runner can compute it as a simple expression
