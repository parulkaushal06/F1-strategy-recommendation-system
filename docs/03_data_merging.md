# Data and feature pipeline

The scripts run from the repository root. Intermediate row counts may change when inputs change; figures here describe the current local snapshot rather than guarantees.

```text
Ergast CSVs → merge_datasets.py → data/interim/lap_level_merged.csv
           → build_features.py → data/processed/lap_level_features.csv
OpenF1 CSVs → consolidate_openf1.py → data/interim/openf1_lap_level.csv
           → final_merge.py → data/processed/final_merged_dataset.csv
           → clean_data.py → data/processed/cleaned_dataset.csv
           → training / FastAPI
```

## 1. Ergast lap table

`merge_datasets.py` uses lap times as the row grain and joins race, result, driver, constructor, circuit, and pit-stop tables. It derives cumulative elapsed time, gap to leader, pit-stop count, tire-age proxy, and the `won` label. Each row represents a driver in a race on one lap.

## 2. Race-state features

`build_features.py` filters to year >= 2011 and derives race progress, position change versus grid and previous lap, rolling lap time, pace delta to the fastest lap on that race lap, gap per lap, tire-age ratio, gap to the car ahead, `drs_zone_proxy`, and `pit_window_proxy`. DRS proxy threshold is 1,250 ms; the leader's zero-gap artifact is excluded.

## 3. OpenF1 consolidation and ID bridge

`consolidate_openf1.py` combines session files, expands stint ranges to per-lap tire records, joins pit data, aligns weather to lap timestamps, and attaches driver mapping data. It coalesces suffixed session/meeting IDs after the weather join and removes duplicate stint boundary rows.

`final_merge.py` maps OpenF1 driver acronyms to Ergast driver IDs and normalized circuit names to 2023 Ergast races, then joins on `(raceId, driverId, lap)`. Overrides are explicit in the script. Missing or unmatched OpenF1 values remain missing; they are not zero-valued observations.

## 4. Cleaning and model-ready table

`clean_data.py` handles duplicate columns/rows, data types, and anomalous lap-time markers. The current local `cleaned_dataset.csv` has 320,274 rows and 66 columns. About 23,431 rows carry OpenF1 enrichment (roughly 7.3%); exact coverage depends on downloaded inputs. The API loads only required columns by default to reduce memory.

Training selects features in `select_feature_columns()` (`src/features/train_model.py`). The stored `models/feature_columns.pkl` defines the deployed model's input names and order.
