# RACECRAFT: F1 Strategy and Win Probability

RACECRAFT analyzes historical Formula 1 races lap by lap. A calibrated Random Forest estimates each driver's win probability; a separate strategy engine adds transparent pit urgency, DRS/ERS proxies, race-craft guidance, and what-if simulations. The web app replays recorded races. It is not connected to live timing and is not a pit-wall decision system.

## Features

- Lap-by-lap win-probability history and field context.
- Pit urgency scoring, DRS availability proxy, ERS proxy, and attack/defend/manage calls.
- Pit timing comparisons and what-if actions: `pit`, `push`, `attack`, `drs`, and `overtake`.
- Driver comparison, race lookup, circuit maps, and historical result pages.
- FastAPI endpoints for model metrics and per-prediction SHAP explanations. SHAP is available through the API but is not currently shown in the dashboard.

Recommendations are not all model outputs. Pit calls and race craft are rules; DRS and ERS are explicitly proxies; push and attack simulations apply stated illustrative assumptions. Read [known limitations](docs/06_known_limitations.md) before interpreting results.

## Architecture and folders

```text
Ergast + OpenF1 → src/data pipeline → feature table → trained model
                                             ↓
web/ (Next.js) ← HTTP/JSON → src/api/ (FastAPI) → StrategyEngine
```

- `src/data/`: collection, merge, cleaning, and export scripts.
- `src/features/`: feature engineering, training, cross-validation, SHAP.
- `src/strategy/`: recommendation and simulation logic.
- `src/api/`: FastAPI service.
- `web/`: Next.js 16 / React 19 / TypeScript / Tailwind frontend.
- `tests/`: synthetic-data pytest suite.
- `tools/`, `notebooks/`: validation utilities and analysis.
- `docs/`, `reports/`, `assets/`: project docs, saved evaluations, circuit assets.
- `data/` and `models/*.pkl`: local generated inputs/artifacts; ignored by Git.

See [docs/00_overview.md](docs/00_overview.md) for the full documentation index.

## Current saved model evaluation

The tracked `models/model_metrics.json` describes training on seasons before 2023, calibration on 2023, and held-out testing on 2024. It records ROC-AUC **0.9746**, Brier score **0.0237**, precision **0.7640**, and recall **0.6884** (at the model's default classification threshold). These are historical evaluation metrics, not a guarantee of future performance. The model's signals are dominated by current position and gaps; see [model results](docs/09_model_results.md) and [baseline comparisons](reports/baseline_comparison.csv).

## Requirements

- Python 3.12 is used in CI and the backend Docker image.
- Python packages: `requirements.txt`; API-only image packages: `requirements-api.txt`; test packages: `requirements-dev.txt`.
- Node.js 22 is used in CI; frontend dependencies and scripts are in `web/package.json`.
- The API requires the cleaned dataset, raw Ergast `races.csv` and `drivers.csv`, and model pickle files. These are not committed.

## Build data and model

Start with the raw Ergast CSV dataset in `data/raw/ergast/`. OpenF1 downloads require network access and are optional for the base historical model, but are needed to reproduce the telemetry enrichment and DRS validation. Run commands from the repository root:

```bash
python src/data/merge_datasets.py
python src/features/build_features.py
python src/data/fetch_openf1.py
python src/data/fetch_openf1_drivers.py
python src/data/fetch_openf1_sessions.py
python src/data/consolidate_openf1.py
python src/data/final_merge.py
python src/data/clean_data.py
python src/features/cross_validate.py   # optional evaluation
python src/features/train_model.py
```

OpenF1 data collection can be skipped if you already have compatible OpenF1 files and only need the Ergast-derived dataset. For details and the exact expected inputs, see [data collection](docs/02_data_collection.md) and [data merging](docs/03_data_merging.md). The production training split is currently fixed to calibration year 2023 and test year 2024, so the dataset must contain both years.

## Run locally

Install dependencies and create the expected data and model files first. The API fails at startup with a helpful missing-file error if these artifacts are absent.

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn src.api.main:app --reload --port 8000
```

In another terminal:

```bash
cd web
npm ci
npm run dev
```

Open `http://localhost:3000`. The frontend defaults to `http://localhost:8000`; set `NEXT_PUBLIC_API_URL` in `web/.env.local` to point it elsewhere. FastAPI docs are at `http://localhost:8000/docs`.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check; supports GET and HEAD |
| `GET /api/seasons`, `/api/races`, `/api/drivers`, `/api/race-info`, `/api/laps` | Dataset lookups |
| `GET /api/strategy` | Current driver state, probability history, field, recommendations |
| `GET /api/compare` | Compare two drivers at a race lap |
| `GET /api/simulate/pit-timings` | Pit now or in 3, 5, or 8 laps |
| `GET /api/simulate/what-if` | Combine `pit`, `push`, `attack`, `drs`, `overtake` |
| `GET /api/explain` | SHAP factors for one prediction |
| `GET /api/model-metrics` | Saved training evaluation JSON |

## Tests and CI

```bash
pytest tests -v
```

Tests build a small synthetic dataset and model, so they do not need the production data bundle. GitHub Actions runs pytest plus frontend lint, TypeScript checking, and build on pushes to `main` and pull requests targeting `main`. Deployment can be triggered through the manual CD workflow.

## Deployment

The frontend is configured for Vercel; the API uses the root Dockerfile and `render.yaml` for Render. On startup, `start.sh` downloads and extracts the archive at `DATA_URL` if required files are missing. Configure `RACECRAFT_CORS_ORIGINS` with the deployed frontend origin and `NEXT_PUBLIC_API_URL` with the API URL. The downloaded archive is created by `tools/make_data_bundle.py` and must include the API's required data and model files.

## Limitations

- The available lap-level data and saved model evaluation run through 2024; Home and Results still use static 2023 content.
- The dashboard replays historical races; there is no live telemetry feed.
- DRS was validated on only two races; ERS has no public ground truth.
- OpenF1 enrichment is sparse (about 7% of rows, concentrated in 2023).
- Driver probabilities are predicted independently and do not sum to 100% per lap.
- 2023 isotonic calibration is a single-season calibration; some 2024 probability buckets remain miscalibrated.
- SHAP explains the raw model's feature contributions while the headline probability comes from the calibrated model.
- Circuit traces are missing for four circuits identified in the dashboard documentation.

See [docs/06_known_limitations.md](docs/06_known_limitations.md) for details.

## Sources and attribution

Race data is sourced from Ergast/Kaggle and OpenF1. Circuit outline SVGs are attributed in [assets/circuits-svg/ATTRIBUTION.md](assets/circuits-svg/ATTRIBUTION.md). This project is not affiliated with Formula 1 or the FIA.
