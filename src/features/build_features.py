"""
src/features/build_features.py

Takes the merged lap-level dataset (data/interim/lap_level_merged.csv) and
engineers features for:
  1. Win probability model
  2. Strategy recommendation engine (pit / DRS / ERS proxies)

Run from project root:
    python src/features/build_features.py
"""

import os
import pandas as pd
import numpy as np

INTERIM_DIR = "data/interim"
PROCESSED_DIR = "data/processed"

os.makedirs(PROCESSED_DIR, exist_ok=True)


def load_merged():
    path = os.path.join(INTERIM_DIR, "lap_level_merged.csv")
    df = pd.read_csv(path)
    print(f"Loaded merged dataset -> {df.shape}")
    return df


def filter_modern_era(df, min_year=2011):
    """Lap-level timing data is sparse/unreliable before ~2011."""
    before = df.shape[0]
    df = df[df["year"] >= min_year].copy()
    print(f"Filtered to year >= {min_year}: {before} -> {df.shape[0]} rows")
    return df


def add_race_progress_features(df):
    """How far into the race this lap is, per race."""
    total_laps = df.groupby("raceId")["lap"].transform("max")
    df["total_laps"] = total_laps
    df["race_progress"] = df["lap"] / df["total_laps"]
    return df


def add_position_features(df):
    """Grid vs current position, and lap-over-lap position change."""
    df = df.sort_values(["raceId", "driverId", "lap"])
    df["position_vs_grid"] = df["grid"] - df["position"]  # positive = gained places
    df["position_change"] = df.groupby(["raceId", "driverId"])["position"].diff().fillna(0)
    return df


def add_pace_features(df, window=3):
    """Rolling average lap time (pace) over the last N laps, per driver per race."""
    df = df.sort_values(["raceId", "driverId", "lap"])
    df["rolling_lap_time_ms"] = (
        df.groupby(["raceId", "driverId"])["milliseconds"]
        .transform(lambda x: x.rolling(window, min_periods=1).mean())
    )
    # Pace relative to the race-leading driver's pace on the same lap
    fastest_on_lap = df.groupby(["raceId", "lap"])["milliseconds"].transform("min")
    df["pace_delta_to_fastest_ms"] = df["milliseconds"] - fastest_on_lap
    return df


def add_gap_features(df):
    """Normalize gap to leader by race progress (early-race gaps mean less)."""
    df["gap_to_leader_s"] = df["gap_to_leader_ms"] / 1000.0
    df["gap_per_lap_covered_s"] = df["gap_to_leader_s"] / df["lap"].replace(0, np.nan)
    df["gap_per_lap_covered_s"] = df["gap_per_lap_covered_s"].fillna(0)
    return df


def add_tire_stint_features(df):
    """laps_since_last_pit already exists as a tire-age proxy from merge_datasets.py."""
    df["tire_age_ratio"] = df["laps_since_last_pit"] / df["total_laps"]
    return df


def add_strategy_proxy_flags(df):
    """
    Rule-based proxy flags for DRS zone and pit window, used before real
    telemetry (OpenF1) is merged in.
    """
    df = df.sort_values(["raceId", "lap", "position"])
    df["gap_to_ahead_ms"] = df.groupby(["raceId", "lap"])["gap_to_leader_ms"].diff().fillna(0)
    df["drs_zone_proxy"] = (df["gap_to_ahead_ms"].abs() <= 1000).astype(int)
    df["pit_window_proxy"] = df["laps_since_last_pit"].between(15, 30).astype(int)
    return df


def build_features():
    df = load_merged()
    df = filter_modern_era(df, min_year=2011)
    df = add_race_progress_features(df)
    df = add_position_features(df)
    df = add_pace_features(df)
    df = add_gap_features(df)
    df = add_tire_stint_features(df)
    df = add_strategy_proxy_flags(df)

    out_path = os.path.join(PROCESSED_DIR, "lap_level_features.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSaved feature-engineered dataset -> {out_path}")
    print(f"Shape: {df.shape}")
    print(df.columns.tolist())
    return df


if __name__ == "__main__":
    build_features()