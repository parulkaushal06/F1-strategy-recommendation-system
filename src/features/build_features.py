"""
src/features/build_features.py

Takes the merged lap-level dataset (data/interim/lap_level_merged.csv) and
engineers features for:
  1. Win probability model
  2. Strategy recommendation engine (pit / DRS / ERS proxies)

Run from project root:
    python src/features/build_features.py
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

INTERIM_DIR = "data/interim"
PROCESSED_DIR = "data/processed"


def load_merged() -> pd.DataFrame:
    path = os.path.join(INTERIM_DIR, "lap_level_merged.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Fix: run `python src/data/merge_datasets.py` first."
        )
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"{path} exists but has 0 rows -- re-run merge_datasets.py.")
    logger.info("Loaded merged dataset -> %s", df.shape)
    return df


def filter_modern_era(df: pd.DataFrame, min_year: int = 2011) -> pd.DataFrame:
    """Lap-level timing data is sparse/unreliable before ~2011."""
    before = df.shape[0]
    df = df[df["year"] >= min_year].copy()
    logger.info("Filtered to year >= %d: %d -> %d rows", min_year, before, df.shape[0])
    if df.empty:
        raise ValueError(
            f"Filtering to year >= {min_year} removed every row. Check the 'year' "
            f"column in the merged dataset actually contains years >= {min_year}."
        )
    return df


def add_race_progress_features(df: pd.DataFrame) -> pd.DataFrame:
    """How far into the race this lap is, per race."""
    total_laps = df.groupby("raceId")["lap"].transform("max")
    df["total_laps"] = total_laps
    df["race_progress"] = df["lap"] / df["total_laps"]
    return df


def add_position_features(df: pd.DataFrame) -> pd.DataFrame:
    """Grid vs current position, and lap-over-lap position change."""
    df = df.sort_values(["raceId", "driverId", "lap"])
    df["position_vs_grid"] = df["grid"] - df["position"]  # positive = gained places
    df["position_change"] = df.groupby(["raceId", "driverId"])["position"].diff().fillna(0)
    return df


def add_pace_features(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
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


def add_gap_features(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize gap to leader by race progress (early-race gaps mean less)."""
    df["gap_to_leader_s"] = df["gap_to_leader_ms"] / 1000.0
    df["gap_per_lap_covered_s"] = df["gap_to_leader_s"] / df["lap"].replace(0, np.nan)
    df["gap_per_lap_covered_s"] = df["gap_per_lap_covered_s"].fillna(0)
    return df


def add_tire_stint_features(df: pd.DataFrame) -> pd.DataFrame:
    """laps_since_last_pit already exists as a tire-age proxy from merge_datasets.py."""
    if "laps_since_last_pit" not in df.columns:
        raise KeyError(
            "'laps_since_last_pit' missing -- expected from merge_datasets.py output. "
            "Re-run the pipeline from the start."
        )
    df["tire_age_ratio"] = df["laps_since_last_pit"] / df["total_laps"]
    return df


def add_strategy_proxy_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rule-based proxy flags for DRS zone and pit window, used before real
    telemetry (OpenF1) is merged in.

    DRS_GAP_THRESHOLD_MS was originally a guess (1000ms, i.e. the "1 second"
    rule DRS is commonly described by). It has since been empirically tuned
    against real DRS telemetry from 2 validated races (see
    tune_drs_threshold.py and docs/06_known_limitations.md section 2):
    1250ms gives the same overall agreement as 1000ms (78.1%) but with
    meaningfully better recall (62.0% vs 54.1%) for a modest increase in
    false positive rate (16.3% vs 13.5%). Tuned against only 2,161 rows from
    2 races -- treated as a reasonable estimate, not a guaranteed season-wide
    optimum.
    """
    DRS_GAP_THRESHOLD_MS = 1250

    df = df.sort_values(["raceId", "lap", "position"])
    df["gap_to_ahead_ms"] = df.groupby(["raceId", "lap"])["gap_to_leader_ms"].diff().fillna(0)
    df["drs_zone_proxy"] = (df["gap_to_ahead_ms"].abs() <= DRS_GAP_THRESHOLD_MS).astype(int)
    df["pit_window_proxy"] = df["laps_since_last_pit"].between(15, 30).astype(int)
    return df


def build_features() -> pd.DataFrame:
    df = load_merged()
    df = filter_modern_era(df, min_year=2011)
    df = add_race_progress_features(df)
    df = add_position_features(df)
    df = add_pace_features(df)
    df = add_gap_features(df)
    df = add_tire_stint_features(df)
    df = add_strategy_proxy_flags(df)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    out_path = os.path.join(PROCESSED_DIR, "lap_level_features.csv")
    df.to_csv(out_path, index=False)
    logger.info("Saved feature-engineered dataset -> %s", out_path)
    logger.info("Shape: %s", df.shape)
    print(df.columns.tolist())
    return df


if __name__ == "__main__":
    try:
        build_features()
    except Exception:
        logger.exception("build_features.py failed.")
        sys.exit(1)