# Autonomous Discovery Build TODO

Last updated: 2026-04-15

## Completed Checkpoints
- [x] Reviewed updated `srs/Requirement.md` and aligned scope to true autonomous discovery.
- [x] Confirmed LLM strategy is **Groq-first** (no Gemini dependency).
- [x] Created this implementation tracker with phase checkpoints.
- [x] Wired runtime client order to use Groq first with Gemini fallback only when available.

## Phase 1 - Discovery Foundation
- [x] Normalize `srs/Requirement.md` text encoding (remove mojibake and wrapper artifacts).
- [x] Refactor discovery flow to infer domain + KPI definitions from headers and sample rows.
- [x] Enforce strict JSON schema for discovery output (`domain`, `kpis`, `cleaning_instructions`, `confidence`).
- [x] Add confidence guardrail and generate `_unanalyzable_error.json` when discovery fails.
- [x] Add schema fingerprint cache key (columns + sample hash + inferred dtypes).
- [x] Persist/reuse cached discovery definitions to avoid repeated LLM calls.

## Phase 2 - Autonomous Cleaning + KPI Engine
- [x] Implement semantic cleaning runner driven by LLM instructions.
- [x] Add safe fallback cleaning (type coercion, null handling, date parsing fallback).
- [x] Build generic KPI computation engine from discovered KPI formulas/aggregations.
- [x] Handle KPI calculation errors as `null` without pipeline crash.

## Phase 3 - Adaptive Analysis
- [ ] Auto-detect time context and compute period-over-period metrics when possible.
- [ ] Add top/bottom performer extraction by discovered KPI dimensions.
- [ ] Add outlier detection (IQR/Z-score) for numeric metrics.
- [ ] Add correlation discovery for numeric columns with significance filtering.
- [ ] Build unified analysis summary JSON for insight/report layers.

## Phase 4 - LLM Insight Layer (Groq-first)
- [ ] Update existing prompt files to work with the new build
- [ ] Upgrade insight prompt to why-driven executive bullets (5-10 bullets).
- [ ] Enforce JSON-only output and salvage valid JSON when response is noisy.
- [ ] Add recommendations generator linked to discovered drivers.
- [ ] Add retry/fallback strategy across configured Groq keys.

## Phase 5 - Dynamic Reporting
- [x] Replace fixed report assumptions with dynamic, discovered KPI sections.
- [x] Make chart selection rule-based + AI-assisted (trend/bar/histogram/scatter/pie).
- [x] Ensure Google Slides reports are generated from discovered domain narrative.
- [ ] Ensure dashboard sheets are generated conditionally based on available structures.
- [x] Apply brand rules when `srs/brand_guideline.md` exists; fallback to clean minimal theme.

## Phase 6 - Reliability + Operations
- [x] Strengthen structured logging for each phase and failure mode.
- [ ] Ensure Drive folder handling for `/processing`, `/processed`, `/failed` remains consistent.
- [x] Validate Supabase history integration for schema-aware comparisons.
- [ ] Verify Modal scheduled/manual runs for full pipeline.
- [ ] Add end-to-end test checklist for at least 3 different dataset domains.

## Definition of Done
- [ ] Any well-formed CSV/XLSX can be analyzed without manual column mapping.
- [ ] Domain and KPI discovery are autonomous and cached.
- [ ] Insights are executive-ready, causal, and JSON-safe.
- [ ] Google Slides + Excel outputs are readable, branded, and non-overlapping.
- [ ] Errors are explicit, recoverable, and never silent.
