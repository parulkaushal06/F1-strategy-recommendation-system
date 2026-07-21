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

import os
import pandas as pd

RAW_DIR = "data/raw/ergast"
INTERIM_DIR = "data/interim"
PROCESSED_DIR = "data/processed"

os.makedirs(INTERIM_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


def load_raw():
    """Load all required Ergast CSVs."""
    files = [
        "races", "results", "drivers", "constructors",
        "qualifying", "pit_stops", "lap_times", "status", "circuits",
    ]
    data = {}
    for f in files:
        path = os.path.join(RAW_DIR, f"{f}.csv")
        data[f] = pd.read_csv(path)
        print(f"Loaded {f}.csv -> {data[f].shape}")
    return data


def build_lap_level_table(data):
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

    return df


def main():
    data = load_raw()
    df = build_lap_level_table(data)

    interim_path = os.path.join(INTERIM_DIR, "lap_level_merged.csv")
    df.to_csv(interim_path, index=False)
    print(f"\nSaved merged lap-level dataset -> {interim_path}")
    print(f"Shape: {df.shape}")
    print(df.head())


if __name__ == "__main__":
    main()