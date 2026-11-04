# Project status snapshot

This page summarizes what is present in the repository now. It replaces the older chronological checklist, which referred to removed paths and pre-calibration model results.

## Implemented

- Historical Ergast lap-level merge and feature engineering under `src/data/` and `src/features/`.
- Optional 2023 OpenF1 telemetry collection, consolidation, ID bridging, and enrichment.
- Cleaned dataset generation with anomalous-lap flagging and data-quality safeguards.
- Calibrated Random Forest training, saved metrics, walk-forward evaluation, baseline comparison, and SHAP explanation code.
- `StrategyEngine` with win probability, pit urgency, DRS/ERS proxies, race-craft calls, pit timing comparison, and combined what-if actions.
- FastAPI lookup, strategy, compare, simulation, explanation, and model-metrics endpoints.
- Next.js dashboard pages: Home, Race Hub, Strategy, Compare, and Results; circuit maps and historical replay controls.
- Synthetic pytest coverage for API validation/error behavior and strategy-engine regressions.
- GitHub Actions CI for backend tests and frontend lint/type-check/build; manual CD workflow and Render Docker configuration.

## Known incomplete items

- Home/season calendar and Results remain static 2023 data; the rest of the dashboard's main race exploration uses the API.
- SHAP endpoint exists but no dashboard view presents its per-prediction factors.
- Model training is fixed to calibration year 2023 and test year 2024; updating the data range needs an explicit new temporal split and evaluation.
- More DRS telemetry, broader calibration seasons, probability normalization, and circuit coverage remain possible improvements.
- Data preparation is script-based; there is no automated scheduled refresh pipeline or live race feed.

## Current saved evaluation reference

`models/model_metrics.json` reports 2024 test ROC-AUC 0.9746, Brier 0.0237, precision 0.7640, recall 0.6884. `reports/cross_validation_results.csv` contains seven walk-forward test seasons (2018–2024). These are saved artifact results and should be regenerated after changing data, features, or model code.
