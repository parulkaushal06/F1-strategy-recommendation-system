# Data collection and rebuild guide

Run scripts from the repository root. Ergast/Kaggle CSVs are downloaded separately and placed in `data/raw/ergast/`; generated datasets are excluded from Git.

## Required Ergast inputs

`merge_datasets.py` requires `races.csv`, `results.csv`, `drivers.csv`, `constructors.csv`, `qualifying.csv`, `pit_stops.csv`, `lap_times.csv`, `status.csv`, and `circuits.csv`. The source mirror may contain additional tables that the current script does not require.

## Optional OpenF1 collection

The collection scripts target 2023 race sessions and write per-session CSVs under `data/raw/openf1/`:

```bash
python src/data/fetch_openf1.py
python src/data/fetch_openf1_drivers.py
python src/data/fetch_openf1_sessions.py
```

`fetch_car_data.py` downloads selected high-frequency telemetry for DRS validation. It is not required to train the base model. Collection requires network access and may be affected by upstream API availability.

## Processing and training order

```bash
python src/data/merge_datasets.py
python src/features/build_features.py
# OpenF1 enrichment (requires the downloaded OpenF1 files)
python src/data/consolidate_openf1.py
python src/data/final_merge.py
python src/data/clean_data.py
python src/features/cross_validate.py   # optional; writes reports/cross_validation_results.csv
python src/features/train_model.py      # current split requires 2023 and 2024
```

`consolidate_openf1.py` expects OpenF1 files and the driver mapping. `final_merge.py` expects the consolidated OpenF1 table, Ergast tables, and feature table. OpenF1 enrichment can be omitted for an intentionally Ergast-only workflow, but the documented merge sequence assumes those files exist.

Training writes raw and calibrated model pickle files, the feature list, and `models/model_metrics.json`. The API also requires `data/processed/cleaned_dataset.csv`, `data/raw/ergast/races.csv`, and `data/raw/ergast/drivers.csv`.

## Deployment bundle

Run `python tools/make_data_bundle.py` on a machine containing all API-required files. It creates `racecraft-data.tar.gz` with paths expected by `start.sh`. Upload the archive somewhere accessible to the Render service and set `DATA_URL`; the archive is not tracked in Git.
