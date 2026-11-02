# 🏎️ F1 Strategy & Win Probability Predictor

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-RandomForest-F7931E?logo=scikitlearn&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-Dashboard-000000?logo=nextdotjs&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-06B6D4?logo=tailwindcss&logoColor=white)
![Deployed on Vercel](https://img.shields.io/badge/Deployed-Vercel-000000?logo=vercel&logoColor=white)

A machine-learning system that re-evaluates a driver's **win probability lap by lap** and turns it into concrete race-engineer-style recommendations: pit, use DRS, use ERS overtake mode, attack, defend, or manage pace.

## 🔗 Live Demo

**👉 [https://f1-strategy-recommendation-system.vercel.app](https://f1-strategy-recommendation-system.vercel.app/)**

---

## 📌 Project Overview

Given the current state of a race (lap number, position, gap to leader, tire age, pit history), the project produces:

1. **Win probability**: the likelihood a given driver wins the race, updated every lap
2. **Strategic recommendation**: the action that improves that probability right now
3. **Feature importance**: which factors actually drive winning, learned from historical data

This goes beyond a static "predict the winner before lights out" model. It behaves more like a race engineer's strategy tool, reacting as the race unfolds.

```
Current Win Probability: 68%

Recommendations:
✓ Pit Stop:     CONSIDER PIT (tires in typical pit window)
✓ DRS:          DRS AVAILABLE
✓ ERS:          USE ERS OVERTAKE MODE (proxy)
✓ Race Craft:   DEFEND POSITION (car behind is within DRS range)
```

## ✨ Features

- **Live win probability** for any driver, at any lap, in any race in the dataset
- **Pit stop recommendation**: data-driven tire-age window plus a continuous urgency score (not a fixed lap count)
- **DRS availability** flag
- **ERS overtake mode** recommendation (clearly labeled as a proxy, since no public ERS data exists)
- **Race-craft recommendation**: attack / defend / defend urgently / manage pace / hold station, using gap ahead, gap behind, pace delta and position trend
- **Feature importance analysis**: position and gap to leader dominate
- **RACECRAFT dashboard**: Next.js + Tailwind app with real circuit maps for 31 tracks
- **Cross-source data validation** between two independent F1 data providers (98.9%–100% agreement on pit stops and driver codes)
- Explicit separation between *measured* signals and *inferred* proxies

## 🗺️ RACECRAFT Dashboard

The web app (`web/`) includes a Season Hub, Race Hub, Strategy Dashboard, Driver Comparison and Results view. It talks to the trained model and `StrategyEngine` through a small FastAPI layer, since a browser can't load a `.pkl` file directly.

Circuit maps are real, not illustrative. 31 of the 35 circuits in the dataset use actual track outlines from [julesr0y/f1-circuits-svg](https://github.com/julesr0y/f1-circuits-svg) (CC BY 4.0, see `assets/circuits-svg/ATTRIBUTION.md`), with corners and sector markers aligned using real FastF1 telemetry (see `tools/circuit-alignment/`). Four circuits (Valencia, Korea, India, Malaysia) have no real map because FastF1 doesn't reliably expose session data for races before about 2018.

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Data & ML | Python, pandas, numpy, scikit-learn (`RandomForestClassifier`), joblib |
| API | FastAPI, uvicorn |
| Frontend | Next.js, Tailwind CSS |
| Telemetry / maps | FastF1 |
| Deployment | Vercel (frontend), Docker + `render.yaml` (backend), GitHub Actions CI/CD |

**Data sources:** [Ergast/Kaggle F1 database](http://ergast.com/mrd/) (1950–2024), [OpenF1 API](https://openf1.org/) (2023 laps, pits, stints, weather, real DRS), [FastF1](https://github.com/theOehrly/Fast-F1) (corner/sector telemetry).

## 📂 Project Structure

```
F1-strategy-recommendation-system/
├── data/
│   ├── raw/                # untouched downloaded data (Ergast CSVs, OpenF1 responses)
│   ├── interim/            # partially merged/cleaned data
│   └── processed/          # final model-ready datasets
├── notebooks/              # data cleaning, EDA, modeling
├── src/
│   ├── data/               # fetch/merge raw data + export JSON for web/
│   ├── features/           # feature engineering + model training
│   ├── strategy/           # strategy recommendation engine
│   └── api/                # FastAPI wrapper around model + StrategyEngine
├── models/                 # saved trained models
├── web/                    # RACECRAFT Next.js + Tailwind dashboard
├── assets/circuits-svg/    # real circuit outlines (CC BY 4.0)
├── tools/circuit-alignment/# aligns FastF1 corner/sector data onto the SVGs
├── tests/                  # test suite
├── docs/                   # full project documentation
├── reports/                # figures and write-ups
├── tools/                     # backtest, DRS validation/tuning, race-craft checks, data bundle
├── src/features/cross_validate.py  # multi-season cross-validation (2018–2024)
├── config.yaml
├── start.sh
├── Dockerfile
├── render.yaml
└── requirements*.txt          # requirements.txt, requirements-api.txt, requirements-dev.txt
```

## ⚙️ Installation

```bash
git clone https://github.com/parulkaushal06/F1-strategy-recommendation-system.git
cd F1-strategy-recommendation-system
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

## ▶️ Running Locally

**1. Start the API**

```bash
uvicorn src.api.main:app --reload --port 8000
```

**2. Start the dashboard** (in a second terminal)

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. The API must be running first. The frontend calls `http://localhost:8000` by default, configurable via `web/.env.local`.

**Use the strategy engine directly in Python**

```python
import pandas as pd
from src.strategy.recommend_action import StrategyEngine

df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)
real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
engine = StrategyEngine(avg_pit_loss_ms=real_pit_durations.median())

row = df.iloc[1000]                      # one driver, one lap
field_df = df[(df["raceId"] == row["raceId"]) & (df["lap"] == row["lap"])]

print(engine.recommend_full(row, same_lap_field_df=field_df))
```

**Rebuild the pipeline from scratch** (raw data must already be in `data/raw/`, see `docs/02_data_collection.md`):

```bash
python src/data/merge_datasets.py       # raw Ergast CSVs -> lap-level dataset
python src/features/build_features.py   # engineer race-state features
python src/data/consolidate_openf1.py   # combine OpenF1 telemetry CSVs
python src/data/final_merge.py          # bridge Ergast <-> OpenF1
python src/data/clean_data.py           # validation, dedup, missing values
python src/features/train_model.py      # train + save win-probability model
```

## 📊 Results

- **Win probability model:** time-based train/test split by season (no future-race leakage). **ROC-AUC 0.976** on the held-out season, stable across other held-out seasons (0.976, 0.991).
- **Calibration:** rows that actually won average **91.4%** predicted probability; rows that didn't average **6.5%**.
- **Early-race performance:** AUC 0.95 in the first 15% of a race, rising to 0.995 in the final 15%.
- **Pit stop recommendation:** **73% recall** on 300 real "lap before an actual pit stop" samples, **0.7% false-positive rate**.
- **Race-craft recommendation:** validated on about 1,150 real driver-lap snapshots; attack chances are rare (~1% of laps), matching real race behavior.

Details: [`docs/09_model_results.md`](docs/09_model_results.md) and [`docs/10_strategy_engine.md`](docs/10_strategy_engine.md).

## 🚀 Deployment

- **Frontend:** deployed on Vercel at [f1-strategy-recommendation-system.vercel.app](https://f1-strategy-recommendation-system.vercel.app/)
- **Backend:** containerised with the included `Dockerfile`, with a `render.yaml` for hosting the FastAPI service
- **CI/CD:** GitHub Actions workflows in `.github/workflows/` (deployment is triggered manually)

## 🔮 Future Improvements

- Systematic hyperparameter search (`max_depth`, `min_samples_leaf`, `n_estimators` are currently hand-picked)
- New signal: driver/constructor form, qualifying gap-to-pole, tire compound and weather beyond the current OpenF1 subset
- Validate `drs_zone_proxy` against more real DRS telemetry (currently 2 races)
- Extend OpenF1 telemetry beyond 2023
- Real circuit maps for the remaining 4 circuits and tighter alignment for Spielberg, Mugello and Baku

> ⚠️ This is a rigorously validated data-science project on historical data, not a live pit-wall tool. That would require proprietary telemetry, live weather radar and physics-based tire models.

See [`docs/06_known_limitations.md`](docs/06_known_limitations.md) and [`docs/07_project_status.md`](docs/07_project_status.md) for the full list.

## 📚 Documentation Index

| File | Contents |
|---|---|
| [`00_overview.md`](docs/00_overview.md) | Project goals and architecture |
| [`01_data_sources.md`](docs/01_data_sources.md) | Dataset origins and coverage limits |
| [`02_data_collection.md`](docs/02_data_collection.md) | Scripts used to download raw data |
| [`03_data_merging.md`](docs/03_data_merging.md) | How raw tables became one dataset |
| [`04_data_cleaning.md`](docs/04_data_cleaning.md) | Cleaning steps and validation |
| [`05_data_dictionary.md`](docs/05_data_dictionary.md) | Every column: meaning, source, type |
| [`06_known_limitations.md`](docs/06_known_limitations.md) | Honest gaps in the data |
| [`07_project_status.md`](docs/07_project_status.md) | What's done, what's next |
| [`08_eda_findings.md`](docs/08_eda_findings.md) | Exploratory analysis findings |
| [`09_model_results.md`](docs/09_model_results.md) | Model performance and feature importance |
| [`10_strategy_engine.md`](docs/10_strategy_engine.md) | Recommendation logic, bugs found and fixed |
| [`11_dashboard.md`](docs/11_dashboard.md) | Dashboard design and how to run it |

## 🙏 Acknowledgements

- Circuit outlines by [julesr0y/f1-circuits-svg](https://github.com/julesr0y/f1-circuits-svg) (CC BY 4.0)
- Data from Ergast, [OpenF1](https://openf1.org/) and [FastF1](https://github.com/theOehrly/Fast-F1)

## 👤 Author

**Parul Kaushal**, [@parulkaushal06](https://github.com/parulkaushal06)
