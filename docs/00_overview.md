# RACECRAFT project overview

RACECRAFT is a historical Formula 1 race-state analysis project. It estimates a driver's probability of winning from lap-level race features and presents rule-based strategy guidance alongside the estimate. It is a replay and analysis dashboard, not a live timing or pit-wall system.

## Current architecture

```text
Ergast/Kaggle CSVs ─┐
                    ├─ data preparation ─ feature engineering ─ trained model
OpenF1 race data ───┘                                      │
                                                          ▼
Browser: Next.js/React/TypeScript ── HTTP/JSON ── FastAPI + StrategyEngine
```

The data pipeline is implemented in `src/data/` and `src/features/`. `src/strategy/recommend_action.py` applies pit, DRS/ERS proxy, race-craft and what-if logic. `src/api/main.py` loads the cleaned dataset and model artifacts at process startup, then exposes read-only GET endpoints. The frontend under `web/src/app/` calls those endpoints through `web/src/lib/api.ts`.

## Repository map

| Path | Contents |
|---|---|
| `src/data/` | Ergast and OpenF1 collection, merging, cleaning, and web-data export scripts |
| `src/features/` | Race-state features, training, walk-forward evaluation, and SHAP explanations |
| `src/strategy/` | `StrategyEngine` recommendations and simulations |
| `src/api/` | FastAPI app, data/model loading, and HTTP endpoints |
| `web/` | Next.js 16, React 19, TypeScript and Tailwind dashboard |
| `tests/` | Synthetic API and strategy-engine tests; no production data required |
| `tools/` | Backtests, baselines, DRS validation/tuning, circuit alignment, data bundling |
| `notebooks/` | Data cleaning, EDA and modeling explorations |
| `data/` | Local raw/interim/processed data; ignored by Git |
| `models/` | Trained pickle artifacts (ignored) and tracked model metrics JSON |
| `reports/` | Saved baseline and cross-validation results |
| `docs/` | Project documentation |
| `assets/circuits-svg/` | Attributed circuit outline assets |
| `.github/workflows/` | CI checks and manually triggered deployment workflow |

## Current data and model snapshot

The checked-in model metrics report a 2024 held-out test year, calibrated on 2023 and trained on earlier seasons: ROC-AUC 0.9746, Brier score 0.0237, precision 0.7640, and recall 0.6884. The metrics JSON records 269,314 training rows, 24,386 calibration rows, and 26,574 test rows. These describe the saved model evaluation, not current-season race results. Local `data/processed/cleaned_dataset.csv` currently has 320,274 rows and 66 columns; `data/` and model pickle files are not tracked.

## Documentation index

| Document | Covers |
|---|---|
| [01 Data sources](01_data_sources.md) | Source tables, temporal coverage, and data caveats |
| [02 Data collection](02_data_collection.md) | Collection scripts and pipeline prerequisites |
| [03 Data merging](03_data_merging.md) | Dataset transformation order and join keys |
| [04 Data cleaning](04_data_cleaning.md) | Cleaning, validation, and known quality checks |
| [05 Data dictionary](05_data_dictionary.md) | Columns in the current cleaned dataset |
| [06 Known limitations](06_known_limitations.md) | Model, data, recommendation, and deployment constraints |
| [07 Project status](07_project_status.md) | Implemented features and remaining work |
| [08 EDA findings](08_eda_findings.md) | Exploratory conclusions and feature selection context |
| [09 Model results](09_model_results.md) | Saved evaluation, baselines, calibration, and CV |
| [10 Strategy engine](10_strategy_engine.md) | Implemented rules and simulation assumptions |
| [11 Dashboard](11_dashboard.md) | Pages, API integration, local run, and deployment |

## Local run

See the root [README](../README.md) for setup and pipeline commands. A fresh clone needs the ignored data and model artifacts before the API can start; either recreate them with the documented pipeline or supply the deployment data bundle.
