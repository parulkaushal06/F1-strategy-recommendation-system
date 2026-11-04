# Project status snapshot

This page summarizes what is present in the repository now. It replaces the older chronological checklist, which referred to removed paths and pre-calibration model results.

## Implemented

- Historical Ergast lap-level merge and feature engineering under `src/data/` and `src/features/`.
- Optional 2023 OpenF1 telemetry collection, consolidation, ID bridging, and enrichment.
- Cleaned dataset generation with anomalous-lap flagging and data-quality safeguards.
- Calibrated Random Forest training with a three-season calibration window, saved library versions, walk-forward evaluation with race-cluster bootstrap intervals, baseline comparison, and SHAP explanation code.
- Field-normalized API probabilities, an on-demand SHAP panel in Strategy, out-of-sample pit precision/FPR reporting, and a `-999` feature-ablation report.
- `StrategyEngine` with win probability, pit urgency, DRS/ERS proxies, race-craft calls, pit timing comparison, and combined what-if actions.
- FastAPI lookup, strategy, compare, simulation, explanation, and model-metrics endpoints.
- Next.js dashboard pages: Home, Race Hub, Strategy, Compare, and Results; circuit maps and historical replay controls.
- Synthetic pytest coverage for API validation/error behavior and strategy-engine regressions.
- GitHub Actions CI for backend tests and frontend lint/type-check/build; manual CD workflow and Render Docker configuration.

## Known incomplete items

- Home/season calendar and Results remain static 2023 data; the rest of the dashboard's main race exploration uses the API.
- Model training is fixed to a 2021–2023 calibration window and 2024 test year; updating the data range needs an explicit new temporal split and evaluation.
- Pit urgency remains a low-precision heuristic (5.4% precision at the `PIT NOW` cutoff in the combined 2021–2024 out-of-sample report); more DRS telemetry and circuit coverage remain possible improvements.
- Field normalization is an API display transformation; it does not make the independently predicted scores a jointly calibrated field model.
- Data preparation is script-based; there is no automated scheduled refresh pipeline or live race feed.

## Current saved evaluation reference

`models/model_metrics.json` reports 2024 test ROC-AUC 0.9754, Brier 0.0222, precision 0.7636, recall 0.6891, and records scikit-learn/pandas versions. Its 24-race evaluation reports 95.8% final-lap winner top-1 accuracy (95% race-bootstrap CI: 83.3–100%). `reports/cross_validation_results.csv` contains seven walk-forward test seasons (2018–2024). Pit OOS and feature-ablation outputs are saved in `reports/pit_oos_evaluation.csv` and `reports/feature_ablation.csv`. Regenerate these artifacts after changing data, features, or model code.
