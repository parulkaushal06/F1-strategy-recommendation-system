"""
src/data/clean_data.py

Script version of notebooks/02_data_cleaning.ipynb, so the full pipeline
(merge -> features -> consolidate -> final_merge -> clean -> train) can be
rerun end-to-end from the command line without opening Jupyter.

See docs/04_data_cleaning.md for the full writeup of every check below.

Run from project root:
    python src/data/clean_data.py
"""

import pandas as pd
import numpy as np
import os

PROCESSED_DIR = "data/processed"
IN_PATH = os.path.join(PROCESSED_DIR, "final_merged_dataset.csv")
OUT_PATH = os.path.join(PROCESSED_DIR, "cleaned_dataset.csv")


def clean():
    df = pd.read_csv(IN_PATH, low_memory=False)
    print("Loaded final merged dataset -> shape:", df.shape)

    # 1. Core identifier check
    core_cols = ["raceId", "driverId", "lap", "position", "grid", "year", "won"]
    nulls = df[core_cols].isnull().sum()
    print("\nCore identifier nulls (should be all 0):")
    print(nulls)

    # 2. Row-level duplicate check
    dupe_key = ["raceId", "driverId", "lap"]
    dupes = df.duplicated(subset=dupe_key, keep=False)
    print(f"\nDuplicate rows on {dupe_key}: {dupes.sum()}")
    if dupes.sum() > 0:
        df = df.drop_duplicates(subset=dupe_key, keep="first")
        print("Dropped duplicates. New shape:", df.shape)

    # 3. Cross-source validation (pit stops, driver code)
    if "pit_stop_this_lap_openf1" in df.columns and "session_key" in df.columns:
        both_present = df[df["session_key"].notna()][["pit_stop_this_lap", "pit_stop_this_lap_openf1"]]
        if len(both_present) > 0:
            agreement_pct = (both_present["pit_stop_this_lap"] == both_present["pit_stop_this_lap_openf1"]).mean() * 100
            print(f"\nPit stop agreement (Ergast vs OpenF1): {agreement_pct:.1f}% ({len(both_present)} rows compared)")

    if "name_acronym" in df.columns and "session_key" in df.columns:
        both_present2 = df[df["session_key"].notna()][["code", "name_acronym"]]
        if len(both_present2) > 0:
            agreement_pct2 = (both_present2["code"] == both_present2["name_acronym"]).mean() * 100
            print(f"Driver code agreement (Ergast vs OpenF1): {agreement_pct2:.1f}% ({len(both_present2)} rows compared)")

    # 4. Drop redundant OpenF1 duplicate columns (kept Ergast versions, cover all years)
    cols_to_drop = ["pit_stop_this_lap_openf1", "full_name", "name_acronym", "team_name"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
    print("\nColumns after dropping duplicates:", df.shape[1])

    # 5. Handle missing values
    pit_cols = ["pit_stop_this_lap", "pit_stop_duration_s", "cumulative_pit_stops", "pit_duration_ms"]
    for col in pit_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    openf1_cols = [c for c in ["compound", "air_temperature", "track_temperature", "rainfall"] if c in df.columns]
    df["has_openf1_telemetry"] = df[openf1_cols].notna().any(axis=1).astype(int)
    print("Rows with real OpenF1 telemetry:", df["has_openf1_telemetry"].sum())
    print("Rows without (Ergast-only):", (df["has_openf1_telemetry"] == 0).sum())

    # 6. Data type enforcement
    int_cols = ["raceId", "driverId", "lap", "position", "grid", "year", "won", "pit_stop_this_lap"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # 7. Anomalous lap time flag (red-flag/safety-car artifacts, flagged not dropped)
    df["anomalous_lap_time"] = (df["milliseconds"] / 1000 > 600).astype(int)
    print("Flagged anomalous laps:", df["anomalous_lap_time"].sum())

    # 8. Final check and save
    print("\nFinal shape:", df.shape)
    df.to_csv(OUT_PATH, index=False)
    print(f"Saved -> {OUT_PATH}")
    return df


if __name__ == "__main__":
    clean()