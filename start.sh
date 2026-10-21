#!/bin/sh
# Container entrypoint for the RACECRAFT API.
# data/ and models/*.pkl are not in git, so on first start we download them
# from DATA_URL (a .tar.gz made with tools/make_data_bundle.py).
set -e

REQUIRED="data/processed/cleaned_dataset.csv
data/raw/ergast/races.csv
data/raw/ergast/drivers.csv
models/win_probability_model_calibrated.pkl
models/win_probability_model_raw.pkl
models/feature_columns.pkl"

missing=0
for f in $REQUIRED; do
  [ -f "$f" ] || missing=1
done

if [ "$missing" = "1" ]; then
  if [ -z "$DATA_URL" ]; then
    echo "ERROR: data/model files are missing and DATA_URL is not set." >&2
    echo "Upload racecraft-data.tar.gz (tools/make_data_bundle.py) and set DATA_URL to its download link." >&2
    exit 1
  fi
  echo "Downloading data bundle..."
  curl -fSL --retry 3 "$DATA_URL" -o /tmp/racecraft-data.tar.gz
  tar -xzf /tmp/racecraft-data.tar.gz -C .
  rm -f /tmp/racecraft-data.tar.gz
fi

exec uvicorn src.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"