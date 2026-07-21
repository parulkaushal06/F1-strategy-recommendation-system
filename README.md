# F1 Strategy & Win Probability Predictor 🏎️

Given the current state of an F1 race — lap number, position, gap to leader,
tire age, pit history — this project predicts:

1. **Win probability** — the likelihood a given driver wins the race, updated lap by lap
2. **Strategic recommendation** — what action improves that probability right now
   (pit, use DRS, use ERS overtake mode, attack, defend, or manage pace)
3. **Feature importance** — which factors actually drive winning, learned from historical data

This goes beyond a static "predict the winner before lights out" model. The goal is a
model that re-evaluates win probability *as the race unfolds*, and turns that into a
concrete recommendation — closer to what a race engineer's strategy tools do than a
one-shot prediction.

## What it looks like

```
Current Win Probability: 68%

Recommendations:
✓ Pit Stop:     CONSIDER PIT (tires in typical pit window)
✓ DRS:          DRS AVAILABLE
✓ ERS:          USE ERS OVERTAKE MODE (proxy)
✓ Race Craft:   DEFEND POSITION (car behind is within DRS range)
```

...updating lap by lap, for any driver, in any race in the dataset — see the
[dashboard](#dashboard).

## Architecture

```
Historical F1 Data (Ergast/Kaggle + OpenF1 API)
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
ML Model (win probability)
        ↓
Feature Importance Analysis
        ↓
Strategy Recommendation Engine (pit / DRS / ERS / race craft)
        ↓
Dashboard
```

## Results

- **Win probability model**: `RandomForestClassifier`, time-based train/test split by
  season (no future-race leakage). ROC-AUC **0.976**. Well calibrated: rows that
  actually won the race average **91.4%** predicted probability; rows that didn't win
  average **6.5%**.
- **Pit stop recommendation**: **73% recall** (correctly flags a pit as due, tested on
  300 real "lap before an actual pit stop" samples) with a **0.7% false-positive rate**
  (fresh tires almost never wrongly flagged).
- **Race-craft recommendation** (attack / defend / manage pace): validated across
  ~1,150 real driver-lap snapshots; distribution matches real race behavior (attacking
  chances genuinely rare, ~1% of laps; leader never wrongly told to attack).

Full write-ups: [`docs/09_model_results.md`](docs/09_model_results.md) and
[`docs/10_strategy_engine.md`](docs/10_strategy_engine.md).

## Project folder structure

```
F1 Sport/
├── data/
│   ├── raw/            # untouched downloaded data (Ergast CSVs, OpenF1 API responses)
│   ├── interim/         # partially merged/cleaned data
│   └── processed/       # final model-ready datasets
├── notebooks/            # step-by-step analysis (data cleaning, EDA, modeling)
├── src/
│   ├── data/             # scripts to fetch and merge raw data
│   ├── features/         # feature engineering + model training scripts
│   └── strategy/          # strategy recommendation engine
├── models/                # saved trained model files
├── dashboard/             # Streamlit dashboard app
├── docs/                  # full project documentation (see index below)
└── reports/               # figures and write-ups
```

## Setup

```bash
git clone <this-repo>
cd "F1 Sport"
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

## Running the pipeline from scratch

Only needed if you want to regenerate the processed data / retrain the model
(e.g. after changing a feature). Raw data must already be in `data/raw/` —
see [`docs/02_data_collection.md`](docs/02_data_collection.md).

```bash
python src/data/merge_datasets.py       # raw Ergast CSVs -> lap-level merged dataset
python src/features/build_features.py   # engineer race-state features
python src/data/consolidate_openf1.py   # combine OpenF1 telemetry CSVs
python src/data/final_merge.py          # bridge Ergast <-> OpenF1, merge telemetry in
python src/data/clean_data.py           # validation, dedup, missing-value handling
python src/features/train_model.py      # train + save win-probability model
```

## Using the strategy engine directly

```python
import pandas as pd
from src.strategy.recommend_action import StrategyEngine

df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)
real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
engine = StrategyEngine(avg_pit_loss_ms=real_pit_durations.median())

row = df.iloc[1000]                                 # one driver, one lap
field_df = df[(df["raceId"] == row["raceId"]) & (df["lap"] == row["lap"])]

result = engine.recommend_full(row, same_lap_field_df=field_df)
print(result)
```

## Dashboard

```bash
streamlit run dashboard/app.py
```

Pick a season, race, and driver, then scrub through the race lap by lap to see win
probability, pit/DRS/ERS/race-craft recommendations, and the full field's state update
in real time. See [`docs/11_dashboard.md`](docs/11_dashboard.md) for details — including
an important note that this **replays real historical races** lap by lap (there's no
live telemetry feed wired in), computing every number the same way a live feed would.

## Documentation index

| File | Contents |
|---|---|
| [`00_overview.md`](docs/00_overview.md) | This project's goals and architecture |
| [`01_data_sources.md`](docs/01_data_sources.md) | Where every dataset came from, and coverage limits |
| [`02_data_collection.md`](docs/02_data_collection.md) | Exact scripts run to download raw data |
| [`03_data_merging.md`](docs/03_data_merging.md) | How separate raw tables became one dataset |
| [`04_data_cleaning.md`](docs/04_data_cleaning.md) | Cleaning steps and validation checks |
| [`05_data_dictionary.md`](docs/05_data_dictionary.md) | Every column — meaning, source, type |
| [`06_known_limitations.md`](docs/06_known_limitations.md) | Honest gaps in the data (e.g. no public ERS data exists) |
| [`07_project_status.md`](docs/07_project_status.md) | What's done, what's next |
| [`08_eda_findings.md`](docs/08_eda_findings.md) | Exploratory analysis findings |
| [`09_model_results.md`](docs/09_model_results.md) | Win-probability model performance and feature importance |
| [`10_strategy_engine.md`](docs/10_strategy_engine.md) | Pit/DRS/ERS/race-craft recommendation logic, bugs found and fixed |
| [`11_dashboard.md`](docs/11_dashboard.md) | Dashboard design and how to run it |

## Known limitations (honest, by design)

This project is explicit about what's measured vs. inferred — see
[`docs/06_known_limitations.md`](docs/06_known_limitations.md) for the full list.
Short version: ERS and (mostly) DRS activation are proxies, since no public data source
exposes real values; OpenF1 telemetry only covers 2023 and a handful of validated races;
lap timing is unreliable before 2011 and excluded accordingly; and the dashboard replays
historical races rather than live ones, since no live feed exists in this project.