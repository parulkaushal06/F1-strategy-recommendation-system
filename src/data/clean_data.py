"""
src/data/clean_data.py

Script version of notebooks/02_data_cleaning.ipynb, so the full pipeline
(merge -> features -> consolidate -> final_merge -> clean -> train) can be
rerun end-to-end from the command line without opening Jupyter.

See docs/04_data_cleaning.md for the full writeup of every check below.

Run from project root:
    python src/data/clean_data.py
"""

import logging
import os
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_DIR = "data/processed"
IN_PATH = os.path.join(PROCESSED_DIR, "final_merged_dataset.csv")
OUT_PATH = os.path.join(PROCESSED_DIR, "cleaned_dataset.csv")

CORE_COLS = ["raceId", "driverId", "lap", "position", "grid", "year", "won"]


def clean() -> pd.DataFrame:
    if not os.path.exists(IN_PATH):
        raise FileNotFoundError(
            f"{IN_PATH} not found. Fix: run `python src/data/final_merge.py` first."
        )
    df = pd.read_csv(IN_PATH, low_memory=False)
    if df.empty:
        raise ValueError(f"{IN_PATH} exists but has 0 rows -- re-run final_merge.py.")
    logger.info("Loaded final merged dataset -> shape: %s", df.shape)

    # 1. Core identifier check -- these must never be null. Previously this
    # only printed the counts without acting on them, so a real data problem
    # here could have silently passed through to a model trained on broken
    # identifiers. Now it fails the run instead.
    missing_cols = [c for c in CORE_COLS if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Expected core columns missing entirely: {missing_cols}")
    nulls = df[CORE_COLS].isnull().sum()
    logger.info("Core identifier nulls (should be all 0):\n%s", nulls)
    if nulls.sum() > 0:
        raise ValueError(
            f"Found nulls in core identifier columns, which should never happen:\n{nulls}\n"
            f"This means something upstream (merge_datasets.py / final_merge.py) "
            f"produced incomplete rows -- fix that before cleaning, don't silently "
            f"drop or fill these."
        )

    # 2. Row-level duplicate check
    dupe_key = ["raceId", "driverId", "lap"]
    dupes = df.duplicated(subset=dupe_key, keep=False)
    logger.info("Duplicate rows on %s: %d", dupe_key, dupes.sum())
    if dupes.sum() > 0:
        df = df.drop_duplicates(subset=dupe_key, keep="first")
        logger.info("Dropped duplicates. New shape: %s", df.shape)

    # 3. Cross-source validation (pit stops, driver code)
    if "pit_stop_this_lap_openf1" in df.columns and "session_key" in df.columns:
        both_present = df[df["session_key"].notna()][["pit_stop_this_lap", "pit_stop_this_lap_openf1"]]
        if len(both_present) > 0:
            agreement_pct = (both_present["pit_stop_this_lap"] == both_present["pit_stop_this_lap_openf1"]).mean() * 100
            logger.info("Pit stop agreement (Ergast vs OpenF1): %.1f%% (%d rows compared)",
                        agreement_pct, len(both_present))
            if agreement_pct < 90:
                logger.warning(
                    "Pit stop agreement dropped below 90%% (%.1f%%) -- this was "
                    "100%% previously (see docs/04_data_cleaning.md). Investigate "
                    "before trusting this run's output.", agreement_pct
                )

    if "name_acronym" in df.columns and "session_key" in df.columns:
        both_present2 = df[df["session_key"].notna()][["code", "name_acronym"]]
        if len(both_present2) > 0:
            agreement_pct2 = (both_present2["code"] == both_present2["name_acronym"]).mean() * 100
            logger.info("Driver code agreement (Ergast vs OpenF1): %.1f%% (%d rows compared)",
                        agreement_pct2, len(both_present2))

    # 4. Drop redundant OpenF1 duplicate columns (kept Ergast versions, cover all years)
    cols_to_drop = ["pit_stop_this_lap_openf1", "full_name", "name_acronym", "team_name"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
    logger.info("Columns after dropping duplicates: %d", df.shape[1])

    # 5. Handle missing values
    pit_cols = ["pit_stop_this_lap", "pit_stop_duration_s", "cumulative_pit_stops", "pit_duration_ms"]
    for col in pit_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    openf1_cols = [c for c in ["compound", "air_temperature", "track_temperature", "rainfall"] if c in df.columns]
    df["has_openf1_telemetry"] = df[openf1_cols].notna().any(axis=1).astype(int)
    logger.info("Rows with real OpenF1 telemetry: %d", df["has_openf1_telemetry"].sum())
    logger.info("Rows without (Ergast-only): %d", (df["has_openf1_telemetry"] == 0).sum())

    # 6. Data type enforcement
    int_cols = ["raceId", "driverId", "lap", "position", "grid", "year", "won", "pit_stop_this_lap"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # 7. Anomalous lap time flag (red-flag/safety-car artifacts, flagged not dropped)
    if "milliseconds" not in df.columns:
        raise KeyError("'milliseconds' column missing -- cannot compute anomalous_lap_time flag.")
    df["anomalous_lap_time"] = (df["milliseconds"] / 1000 > 600).astype(int)
    logger.info("Flagged anomalous laps: %d", df["anomalous_lap_time"].sum())

    # 8. Final check and save
    logger.info("Final shape: %s", df.shape)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    logger.info("Saved -> %s", OUT_PATH)
    return df


if __name__ == "__main__":
    try:
        clean()
    except Exception:
        logger.exception("clean_data.py failed.")
        sys.exit(1)