"""
src/data/merge_datasets.py

Builds a per-driver-per-lap dataset for F1 win-probability modeling.

Each output row = (raceId, driverId, lap) with:
  - current race position, gap to leader, lap time
  - pit stop / tire-stint features
  - starting grid position
  - constructor / circuit / season context
  - label: won (1 if this driver finished P1 in this race, else 0)

Run from project root:
    python src/data/merge_datasets.py
"""

import logging
import os
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = "data/raw/ergast"
INTERIM_DIR = "data/interim"
PROCESSED_DIR = "data/processed"

REQUIRED_RAW_FILES = [
    "races", "results", "drivers", "constructors",
    "qualifying", "pit_stops", "lap_times", "status", "circuits",
]

# Columns the rest of the pipeline (build_features.py, clean_data.py,
# recommend_action.py) depends on existing in the output. If any of these
# end up missing or entirely null, something upstream broke silently and
# should fail loudly here instead of surfacing as a confusing error two
# scripts later.
REQUIRED_OUTPUT_COLUMNS = [
    "raceId", "driverId", "lap", "position", "grid",
    "gap_to_leader_ms", "pit_stop_this_lap", "laps_since_last_pit", "won",
]


def load_raw() -> dict:
    """Load all required Ergast CSVs, failing with a clear, actionable message
    if any are missing rather than a raw FileNotFoundError three frames deep."""
    data = {}
    for f in REQUIRED_RAW_FILES:
        path = os.path.join(RAW_DIR, f"{f}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required raw file not found: {path}\n"
                f"Fix: run the Ergast data collection step first "
                f"(see docs/02_data_collection.md) before this script."
            )
        try:
            data[f] = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            raise ValueError(f"{path} exists but is empty. Re-download it and try again.")
        if data[f].empty:
            logger.warning("%s.csv loaded with 0 rows -- this is likely a problem.", f)
        logger.info("Loaded %s.csv -> %s", f, data[f].shape)
    return data


def build_lap_level_table(data: dict) -> pd.DataFrame:
    laps = data["lap_times"].copy()
    races = data["races"][["raceId", "year", "round", "circuitId", "name", "date"]]
    results = data["results"][
        ["raceId", "driverId", "constructorId", "grid", "positionOrder", "statusId", "points"]
    ]
    drivers = data["drivers"][["driverId", "driverRef", "code", "forename", "surname"]]
    constructors = data["constructors"][["constructorId", "name"]].rename(
        columns={"name": "constructor_name"}
    )
    circuits = data["circuits"][["circuitId", "name", "location", "country"]].rename(
        columns={"name": "circuit_name"}
    )
    pit_stops = data["pit_stops"][["raceId", "driverId", "lap", "stop", "milliseconds"]].rename(
        columns={"milliseconds": "pit_duration_ms"}
    )

    # ---- 1. Base: lap_times joined with race + driver context ----
    df = laps.merge(races, on="raceId", how="left")
    df = df.merge(results, on=["raceId", "driverId"], how="left")
    df = df.merge(drivers, on="driverId", how="left")
    df = df.merge(constructors, on="constructorId", how="left")
    df = df.merge(circuits, on="circuitId", how="left")

    if df.empty:
        raise RuntimeError(
            "Merging lap_times with races/results/drivers/constructors/circuits "
            "produced 0 rows. Check that raceId/driverId/constructorId/circuitId "
            "values actually overlap between these raw files (e.g. a partial or "
            "mismatched download)."
        )

    # ---- 2. Gap to leader per lap ----
    # lap_times.milliseconds = time taken for that single lap
    # cumulative time per driver per race gives running total
    df = df.sort_values(["raceId", "driverId", "lap"])
    df["cum_time_ms"] = df.groupby(["raceId", "driverId"])["milliseconds"].cumsum()

    leader_time = (
        df.groupby(["raceId", "lap"])["cum_time_ms"]
        .min()
        .reset_index()
        .rename(columns={"cum_time_ms": "leader_cum_time_ms"})
    )
    df = df.merge(leader_time, on=["raceId", "lap"], how="left")
    df["gap_to_leader_ms"] = df["cum_time_ms"] - df["leader_cum_time_ms"]

    # ---- 3. Pit stop features ----
    pit_stops["pit_stop_this_lap"] = 1
    df = df.merge(
        pit_stops[["raceId", "driverId", "lap", "pit_stop_this_lap", "pit_duration_ms"]],
        on=["raceId", "driverId", "lap"],
        how="left",
    )
    df["pit_stop_this_lap"] = df["pit_stop_this_lap"].fillna(0).astype(int)
    df["pit_duration_ms"] = df["pit_duration_ms"].fillna(0)

    df = df.sort_values(["raceId", "driverId", "lap"])
    df["cumulative_pit_stops"] = df.groupby(["raceId", "driverId"])["pit_stop_this_lap"].cumsum()

    # laps_since_last_pit: tire age AT this lap, i.e. how many laps have been run
    # on the current tires as of this lap. A pit lap should record the tire age
    # the driver had BEFORE pitting (that's the real decision-relevant value),
    # then the counter resets starting the NEXT lap.
    #
    # BUG FIX: an earlier version reset the counter to 0 on the same row a pit
    # happened, so every real pit-stop row recorded laps_since_last_pit == 0
    # (verified: 100% of 11,371 real pit stops). That destroyed the tire-age
    # signal on exactly the rows that matter most for strategy modeling and
    # broke the pit-window heuristic in src/strategy/recommend_action.py,
    # which could never see a pit-stop row with realistic tire age. Fixed by
    # recording the pre-pit counter value on the pit row itself, THEN resetting.
    def laps_since_pit(group):
        counter = 0
        out = []
        for pit in group["pit_stop_this_lap"]:
            out.append(counter)  # tire age as of THIS lap, before any reset
            if pit == 1:
                counter = 0
            else:
                counter += 1
        return out

    df["laps_since_last_pit"] = (
        df.groupby(["raceId", "driverId"], group_keys=False).apply(laps_since_pit).explode().values
    )

    # Regression guard for the bug described above: fail loudly, at build time,
    # if it ever comes back, instead of only being caught by chance months
    # later during manual spot-checking (see tests/test_data_pipeline.py for
    # the automated version of this same check).
    real_pit_rows = df[df["pit_stop_this_lap"] == 1]
    if len(real_pit_rows) > 0:
        zero_tire_age_share = (real_pit_rows["laps_since_last_pit"] == 0).mean()
        if zero_tire_age_share > 0.5:
            raise RuntimeError(
                f"{zero_tire_age_share:.0%} of real pit-stop rows have "
                f"laps_since_last_pit == 0 -- this is the exact tire-age reset "
                f"bug that was fixed before (see the comment above). Something "
                f"has regressed; do not proceed to build_features.py with this "
                f"output."
            )

    # ---- 4. Label: did this driver win the race? ----
    df["won"] = (df["positionOrder"] == 1).astype(int)

    # ---- 5. Tidy column selection ----
    final_cols = [
        "raceId", "year", "round", "circuit_name", "location", "country", "date",
        "driverId", "driverRef", "code", "constructor_name",
        "lap", "position", "grid",
        "milliseconds", "cum_time_ms", "gap_to_leader_ms",
        "pit_stop_this_lap", "cumulative_pit_stops", "laps_since_last_pit", "pit_duration_ms",
        "statusId", "points", "positionOrder", "won",
    ]
    df = df[[c for c in final_cols if c in df.columns]]

    missing_required = [c for c in REQUIRED_OUTPUT_COLUMNS if c not in df.columns]
    if missing_required:
        raise RuntimeError(f"Output is missing required columns: {missing_required}")

    return df


def main():
    os.makedirs(INTERIM_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    logger.info("Loading raw Ergast CSVs from %s...", RAW_DIR)
    data = load_raw()

    logger.info("Building lap-level table...")
    df = build_lap_level_table(data)

    interim_path = os.path.join(INTERIM_DIR, "lap_level_merged.csv")
    df.to_csv(interim_path, index=False)
    logger.info("Saved merged lap-level dataset -> %s", interim_path)
    logger.info("Shape: %s", df.shape)
    print(df.head())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("merge_datasets.py failed.")
        sys.exit(1)