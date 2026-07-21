# 🏎️ F1 Strategy & Win Probability Predictor

## 📌 Project Overview

Given the current state of an F1 race — lap number, position, gap to leader, tire
age, pit history — this project predicts:

1. **Win probability** — the likelihood a given driver wins the race, updated lap by lap
2. **Strategic recommendation** — what action improves that probability right now
   (pit, use DRS, use ERS overtake mode, attack, defend, or manage pace)
3. **Feature importance** — which factors actually drive winning, learned from historical data

This goes beyond a static "predict the winner before lights out" model. The goal is
a model that re-evaluates win probability *as the race unfolds*, and turns that into
a concrete recommendation — closer to what a race engineer's strategy tools do than
a one-shot prediction.

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
- **Pit stop recommendation** — data-driven tire-age window + continuous urgency score
  (not a fixed lap count), validated at 73% recall / 0.7% false-positive rate
- **DRS availability** flag
- **ERS Overtake Mode** recommendation (clearly labeled proxy — no public ERS data exists)
- **Race-craft recommendation** — attack / defend / defend urgently / manage pace / hold
  station, using gap-to-car-ahead, gap-to-car-behind, pace delta, and position trend
- **Feature importance analysis** — what actually drives winning (position and gap to
  leader dominate)
- **Interactive Streamlit dashboard** — pick a season, race, and driver, then scrub
  lap by lap through a real historical race and watch every number update live
- Cross-source data validation between two independent F1 data providers
  (98.9%–100% agreement on pit stops and driver codes)
- Explicit, documented separation between *measured* signals and *inferred* proxies

## 🛠️ Technologies Used

- **Python** — pandas, numpy
- **scikit-learn** — `RandomForestClassifier` for win probability
- **Streamlit** — interactive dashboard
- **Plotly** — live charts inside the dashboard
- **joblib** — model persistence
- **Data sources** — [Ergast/Kaggle F1 historical database](http://ergast.com/mrd/) (1950–2024),
  [OpenF1 API](https://openf1.org/) (2023 telemetry: laps, pits, stints, weather, real DRS)

## 📂 Project Structure

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

## ⚙️ Installation

```bash
git clone <this-repo>
cd "F1 Sport"
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

## ▶️ How to Run

**Run the dashboard:**
```bash
streamlit run dashboard/app.py
```
Opens at `http://localhost:8501`. Pick a season → race → driver, then move the lap
slider to see win probability and recommendations update live.

**Use the strategy engine directly in Python:**
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

**Rerun the full pipeline from scratch** (only needed after changing raw data or a
feature — raw data must already be in `data/raw/`, see `docs/02_data_collection.md`):
```bash
python src/data/merge_datasets.py       # raw Ergast CSVs -> lap-level merged dataset
python src/features/build_features.py   # engineer race-state features
python src/data/consolidate_openf1.py   # combine OpenF1 telemetry CSVs
python src/data/final_merge.py          # bridge Ergast <-> OpenF1, merge telemetry in
python src/data/clean_data.py           # validation, dedup, missing-value handling
python src/features/train_model.py      # train + save win-probability model
```

## 📊 Results

- **Win probability model**: `RandomForestClassifier`, time-based train/test split by
  season (no future-race leakage). **ROC-AUC 0.976** on the held-out season, and stable
  across other held-out seasons tested (0.976, 0.991) — not a lucky split.
- **Calibration**: rows that actually won the race average **91.4%** predicted
  probability; rows that didn't win average **6.5%**.
- **Holds up early in the race, not just late**: AUC 0.95 in the first 15% of a race,
  rising to 0.995 by the final 15% — it isn't just confirming the obvious once someone
  is already clearly winning.
- **Pit stop recommendation**: **73% recall** (flags a pit as due, tested on 300 real
  "lap before an actual pit stop" samples), **0.7% false-positive rate** (fresh tires
  almost never wrongly flagged).
- **Race-craft recommendation**: validated across ~1,150 real driver-lap snapshots —
  distribution matches real race behavior (attacking chances genuinely rare, ~1% of
  laps; leader never wrongly told to attack after a bug fix).


Full write-ups: [`docs/09_model_results.md`](docs/09_model_results.md) and
[`docs/10_strategy_engine.md`](docs/10_strategy_engine.md).

## 🚀 Future Improvements

- **Remove a duplicate feature**: `gap_to_leader_ms` and `gap_to_leader_s` are the same
  value in two units, both currently fed to the model — real redundancy, not signal
- **Proper multi-season cross-validation**, reporting mean ± std AUC across several
  held-out seasons instead of a single test year
- **Hyperparameter tuning** (grid/random search over `max_depth`, `min_samples_leaf`,
  `n_estimators`) — likely modest gains, but standard practice worth formalizing
- **New signal, not just tuning** — this is expected to matter more than the above:
  - Driver / constructor recent-form and historical win-rate features
  - Qualifying gap-to-pole (not just grid slot)
  - Real tire compound and weather data beyond the current 1,357-row OpenF1 subset
- **Validate `drs_zone_proxy`** against the real DRS data already collected for 3 races
- **Extend OpenF1 telemetry coverage** beyond 2023 and beyond 3 validated races
- Be clear this project is a rigorously validated data-science exercise on historical
  data, not a live pit-wall tool — closing that gap would need proprietary telemetry,
  live weather radar, and physics-based tire models no public dataset provides

See [`docs/06_known_limitations.md`](docs/06_known_limitations.md) and
[`docs/07_project_status.md`](docs/07_project_status.md) for the full, honest list.


## 📚 Documentation Index

| File | Contents |
|---|---|
| [`00_overview.md`](docs/00_overview.md) | Project goals and architecture |
| [`01_data_sources.md`](docs/01_data_sources.md) | Where every dataset came from, and coverage limits |
| [`02_data_collection.md`](docs/02_data_collection.md) | Exact scripts run to download raw data |
| [`03_data_merging.md`](docs/03_data_merging.md) | How separate raw tables became one dataset |
| [`04_data_cleaning.md`](docs/04_data_cleaning.md) | Cleaning steps and validation checks |
| [`05_data_dictionary.md`](docs/05_data_dictionary.md) | Every column — meaning, source, type |
| [`06_known_limitations.md`](docs/06_known_limitations.md) | Honest gaps in the data |
| [`07_project_status.md`](docs/07_project_status.md) | What's done, what's next |
| [`08_eda_findings.md`](docs/08_eda_findings.md) | Exploratory analysis findings |
| [`09_model_results.md`](docs/09_model_results.md) | Model performance and feature importance |
| [`10_strategy_engine.md`](docs/10_strategy_engine.md) | Recommendation logic, bugs found and fixed |
| [`11_dashboard.md`](docs/11_dashboard.md) | Dashboard design and how to run it |
