# Project: Autonomous Self-Healing Data Analyst Agent (True Discovery Edition)

## 1. Objective
Build an agentic workflow that monitors a Google Drive folder for new Excel files, automatically discovers the business domain and key performance indicators (KPIs) from any dataset, performs semantic data cleaning, generates insights using an LLM, and produces a professional PowerPoint report and Excel dashboard without hardcoded column mappings or predefined KPIs.

## 2. Tech Stack (Free Tiers / Trials Allowed)
- Orchestration: Python (Modal) + Prefect (optional)
- Storage: Google Drive API
- LLM Engine: Groq (trial credits)
- Data Processing: Pandas, Polars (for larger files)
- Presentation Generation: Python PPTX (or Google Slides API alternative)
- Excel Dashboard: XlsxWriter (or Google Sheets)
- Visualization: Plotly + Kaleido (static PNG exports)
- Real-time Trigger (optional): Pipedream (free tier: 10k invocations/month)
- Hosting: Modal.com (serverless, cron, free 1000 hours/month)
- LLM Response Caching: DiskCache (persistent across runs)

## 3. Core Workflow (Truly Self-Healing Agentic Loop)

### Phase 1: Watcher Trigger
- Poll Google Drive folder for new `.xlsx` or `.csv` files.
- Move in-progress files to `/processing`.
- Maintain a processed log to avoid duplicate runs.

### Phase 2: Autonomous Schema Discovery and KPI Inference
Instead of mapping to fixed columns (for example, `Revenue` or `Date`), the agent does this:

1. Read raw headers and sample data (first 100 rows).
2. Send a discovery prompt to the LLM with no predefined KPI names:
   - Detect business domain.
   - Propose 3 to 5 KPIs with source columns and aggregation logic.
   - Flag cleaning issues and type fixes.
3. Apply semantic cleaning from returned instructions.
4. Cache discovered KPI definition keyed by schema fingerprint.
5. If discovery fails or confidence is too low, write `_unanalyzable_error.json` and stop cleanly.

Expected LLM JSON:
- `domain`
- `kpis` list of objects with `name`, `columns`, `aggregation`, `description`
- `cleaning_instructions`
- `confidence`

### Phase 3: Autonomous Analysis and Insight Generation
After KPI discovery:

1. Compute KPI values from cleaned data.
2. Auto-generate derived analysis where possible:
   - Time trends
   - Distribution and outliers (IQR or Z-score)
   - Correlations between numeric columns
   - Top and bottom performer comparisons
3. Build a summary JSON with KPI values, outliers, trends, correlations, and comparisons.
4. Ask LLM for executive bullets explaining why the numbers moved, not just what moved.

### Phase 4: Adaptive Visualizations and Presentation
- Dynamic chart selection by data shape:
  - Time data -> line chart
  - Categories <= 12 -> bar chart
  - Distribution -> histogram
  - Relationship -> scatter
- Dynamic slide generation per discovered domain and KPI (no fixed template).
- Excel dashboard workbook with adaptive sheets:
  - KPI scorecard
  - Top and bottom performers
  - Trends (if time data exists)
  - Raw or pivoted support data
- Apply `brand_guideline.md` if available, otherwise use a clean fallback theme.

## 4. True Self-Healing Behavior Examples
- HR-like dataset -> infer attrition and tenure-related KPIs.
- Retail-like dataset -> infer sales, returns, and SKU-region patterns.
- IT ops dataset -> infer utilization and error-rate KPIs.

No human should need to predefine KPI names or column mappings.

## 5. Technical Implementation Direction
- Use modular components for:
  - Schema discovery
  - Semantic cleaning
  - KPI computation
  - Adaptive analytics
  - Insight generation
  - Report rendering
- Prioritize Groq-first prompts and strict JSON response handling.
- Use cache-first behavior for repeated schemas.

## 6. Error Handling and Logging (Strict)
- KPI discovery fails -> write `_unanalyzable_error.json`, stop pipeline for that file.
- Cleaning failures -> log per-column issue and continue with safe fallback.
- Missing branding file -> warn and continue with fallback design.
- KPI math failure (for example, division by zero) -> set value to `null` and continue.
- No silent failures.

## 7. Deployment and Execution (Modal)
- Run as scheduled serverless job on Modal.
- Poll source folder, process each new file, and publish outputs.
- Keep secrets in Modal secret store.
- Keep behavior deterministic and observable through logs.

## 8. Success Criteria
- Agent can ingest any well-formed CSV or XLSX and produce relevant analysis.
- Domain and KPI inference are autonomous and schema-aware.
- No manual KPI or column configuration required.
- Reports are polished, branded when possible, and executive-ready.
- Failures are explicit, logged, and recoverable.
