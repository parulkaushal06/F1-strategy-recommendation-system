# F1 Strategy & Win Probability Predictor — Project Documentation

## What this project does

Given the current state of an F1 race (lap number, position, gap to leader, tire age,
pit history), this project predicts:

1. **Win probability** — the likelihood a given driver wins the race, updated lap by lap
2. **Strategic recommendation** — what action improves that probability (pit now, expect
   a DRS opportunity, etc.)
3. **Feature importance** — which factors actually drive winning, learned from historical data

This goes beyond a static "predict the race winner before lights out" model — the goal is
a model that re-evaluates win probability *as the race unfolds*, similar to what broadcast
graphics show live during a Grand Prix.

## Architecture

```
Historical F1 Data (Ergast/Kaggle + OpenF1 API)
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
ML Model
        ↓
Feature Importance Analysis
        ↓
Strategy Recommendation Engine
        ↓
Winning Probability Prediction
        ↓
Dashboard
```

## Objectives

1. Find which factors contribute most to victory (feature importance)
2. Predict winning probability at any point in a race
3. Recommend which car setting or strategic action should be taken
4. Present all of this in a live-updating dashboard

## Documentation index

| File | Contents |
|---|---|
| [`01_data_sources.md`](01_data_sources.md) | Where every dataset came from, why two sources were used, and their coverage limits |
| [`02_data_collection.md`](02_data_collection.md) | Exact scripts run, in order, to download raw data |
| [`03_data_merging.md`](03_data_merging.md) | How separate raw tables became one unified dataset, and the ID-bridging logic used |
| [`04_data_cleaning.md`](04_data_cleaning.md) | Cleaning steps applied, and the validation checks run before each fix |
| [`05_data_dictionary.md`](05_data_dictionary.md) | Every column in the final dataset — meaning, source, type |
| [`06_known_limitations.md`](06_known_limitations.md) | Honest gaps in the data (e.g. no real ERS data exists publicly anywhere) |
| [`07_project_status.md`](07_project_status.md) | What's done, what's next |

## Project folder structure

```
f1-strategy-predictor/
├── data/
│   ├── raw/            # untouched downloaded data (Ergast CSVs, OpenF1 API responses)
│   ├── interim/         # partially merged/cleaned data
│   └── processed/       # final model-ready datasets
├── notebooks/            # step-by-step analysis (data cleaning, EDA, modeling)
├── src/
│   ├── data/             # scripts to fetch and merge raw data
│   └── features/         # feature engineering scripts
├── models/                # saved trained model files
├── dashboard/             # Streamlit dashboard app
├── docs/                  # this documentation
└── reports/               # figures and write-ups
```