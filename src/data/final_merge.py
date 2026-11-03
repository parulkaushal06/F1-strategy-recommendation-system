"""
src/data/final_merge.py

Joins your two datasets into one unified table:
  1. data/processed/lap_level_features.csv   (Ergast, 2011-2024, all races)
  2. data/interim/openf1_lap_level.csv        (OpenF1, 2023 only, richer telemetry)

Because the two sources use different IDs (Ergast: driverId, raceId |
OpenF1: driver_number, session_key), we bridge them using:
  - driver 3-letter code  (Ergast `code`  <->  OpenF1 `name_acronym`)
  - circuit name          (Ergast `circuitRef`  <->  OpenF1 `race_label`)

Run from project root, after merge_datasets.py, build_features.py, and
consolidate_openf1.py have all completed:
    python src/data/final_merge.py
"""

import os
import pandas as pd
import numpy as np

RAW_ERGAST_DIR = "data/raw/ergast"
INTERIM_DIR = "data/interim"
PROCESSED_DIR = "data/processed"

os.makedirs(PROCESSED_DIR, exist_ok=True)


def build_driver_map():
    """Bridge Ergast driverId <-> OpenF1 driver_number using 3-letter code."""
    ergast_drivers = pd.read_csv(os.path.join(RAW_ERGAST_DIR, "drivers.csv"))
    openf1 = pd.read_csv(os.path.join("data/raw/openf1", "2023_drivers_mapping.csv"))

    ergast_drivers["code_clean"] = ergast_drivers["code"].astype(str).str.upper().str.strip()
    openf1["code_clean"] = openf1["name_acronym"].astype(str).str.upper().str.strip()

    driver_map = openf1[["driver_number", "code_clean"]].drop_duplicates().merge(
        ergast_drivers[["driverId", "code_clean", "forename", "surname"]],
        on="code_clean",
        how="left",
    )

    unmatched = driver_map[driver_map["driverId"].isna()]
    if not unmatched.empty:
        print(f"WARNING: {unmatched['code_clean'].nunique()} driver codes did not match Ergast:")
        print(unmatched["code_clean"].unique())

    matched = driver_map.dropna(subset=["driverId"])
    print(f"Driver mapping: {matched.shape[0]} matched rows "
          f"({matched['driver_number'].nunique()} unique drivers)")
    return driver_map[["driver_number", "driverId"]].drop_duplicates()


def build_race_map():
    """Bridge Ergast raceId <-> OpenF1 session_key using circuit name matching."""
    circuits = pd.read_csv(os.path.join(RAW_ERGAST_DIR, "circuits.csv"))
    races = pd.read_csv(os.path.join(RAW_ERGAST_DIR, "races.csv"))
    races_2023 = races[races["year"] == 2023].merge(circuits, on="circuitId", how="left")

    sessions_path = os.path.join("data/raw/openf1", "2023_sessions.csv")
    if not os.path.exists(sessions_path):
        print("ERROR: data/raw/openf1/2023_sessions.csv not found. "
              "Run fetch_openf1_sessions.py first.")
        return pd.DataFrame(columns=["session_key", "raceId"])

    sessions = pd.read_csv(sessions_path)
    sessions["circuit_clean"] = sessions["circuit_short_name"].astype(str).str.lower().str.strip()
    races_2023["circuitRef_clean"] = races_2023["circuitRef"].astype(str).str.lower().str.strip()

    # Manual overrides for known OpenF1 <-> Ergast naming mismatches
    MANUAL_MAP = {
        "sakhir": "bahrain",
        "melbourne": "albert_park",
        "monte carlo": "monaco",
        "montreal": "villeneuve",
        "spielberg": "red_bull_ring",
        "spa-francorchamps": "spa",
        "singapore": "marina_bay",
        "lusail": "losail",
        "austin": "americas",
        "mexico city": "rodriguez",
        "las vegas": "vegas",
        "yas marina circuit": "yas_marina",
        # "imola" intentionally omitted — Emilia Romagna GP was cancelled in 2023
    }
    sessions["circuit_clean"] = sessions["circuit_clean"].replace(MANUAL_MAP)

    race_map = sessions[["session_key", "circuit_clean", "circuit_short_name"]].merge(
        races_2023[["raceId", "circuitRef_clean"]],
        left_on="circuit_clean",
        right_on="circuitRef_clean",
        how="left",
    )

    unmatched = race_map[race_map["raceId"].isna()]
    if not unmatched.empty:
        print(f"WARNING: {len(unmatched)} OpenF1 sessions still unmatched after manual overrides:")
        print(unmatched[["session_key", "circuit_short_name"]])
        unmatched.to_csv(os.path.join(INTERIM_DIR, "race_map_manual_fix.csv"), index=False)

    matched = race_map.dropna(subset=["raceId"])
    dupe_races = matched.groupby("raceId")["session_key"].nunique()
    dupes = dupe_races[dupe_races > 1]
    if len(dupes):
        print(f"NOTE: {len(dupes)} raceId(s) matched by more than one session_key "
              f"(likely sprint-weekend duplicates) — this is fine, just informational.")

    print(f"Race mapping: {matched.shape[0]} sessions matched to {matched['raceId'].nunique()} raceIds")
    return race_map[["session_key", "raceId"]].drop_duplicates()


def main():
    print("Step 1: Building driver mapping...")
    driver_map = build_driver_map()

    print("\nStep 2: Building race mapping...")
    race_map = build_race_map()

    print("\nStep 3: Loading datasets...")
    openf1 = pd.read_csv(os.path.join(INTERIM_DIR, "openf1_lap_level.csv"))
    ergast = pd.read_csv(os.path.join(PROCESSED_DIR, "lap_level_features.csv"))

    # BUGFIX: openf1_lap_level.csv can contain split session_key / session_key_x /
    # session_key_y columns (a side effect of the weather merge_asof step in
    # consolidate_openf1.py). Rows that successfully got weather data ended up with
    # session_key_x/_y instead of plain session_key, which meant they were silently
    # excluded from race matching below. Coalesce BEFORE using session_key for anything.
    for base_col in ["session_key", "meeting_key"]:
        suffixed = [c for c in [f"{base_col}_x", f"{base_col}_y"] if c in openf1.columns]
        if suffixed:
            if base_col not in openf1.columns:
                openf1[base_col] = np.nan
            for c in suffixed:
                openf1[base_col] = openf1[base_col].combine_first(openf1[c])
            openf1 = openf1.drop(columns=suffixed)
    print(f"After coalescing session_key/meeting_key: {openf1['session_key'].notna().sum()} "
          f"rows have a usable session_key")

    print("\nStep 4: Applying mappings to OpenF1 data...")
    openf1 = openf1.merge(driver_map, on="driver_number", how="left")
    openf1 = openf1.merge(race_map, on="session_key", how="left")

    before = openf1.shape[0]
    openf1_matched = openf1.dropna(subset=["driverId", "raceId"])
    print(f"OpenF1 rows with successful driverId+raceId match: "
          f"{openf1_matched.shape[0]} / {before}")

    if openf1_matched.empty:
        print("\nNo rows matched — saving mapping diagnostics only. "
              "Check data/interim/race_map_manual_fix.csv and fix circuit name "
              "matching before re-running.")
        return

    openf1_matched = openf1_matched.rename(columns={"lap_number": "lap"})
    openf1_matched["driverId"] = openf1_matched["driverId"].astype(int)
    openf1_matched["raceId"] = openf1_matched["raceId"].astype(int)

    print("\nStep 5: Merging OpenF1 telemetry onto Ergast lap-level features...")
    final = ergast.merge(
        openf1_matched,
        on=["raceId", "driverId", "lap"],
        how="left",
        suffixes=("", "_openf1"),
    )

    out_path = os.path.join(PROCESSED_DIR, "final_merged_dataset.csv")
    final.to_csv(out_path, index=False)
    print(f"\nSaved final merged dataset -> {out_path}")
    print(f"Shape: {final.shape}")
    print(f"Rows with OpenF1 telemetry enrichment: {final['compound'].notna().sum() if 'compound' in final.columns else 'N/A'}")


if __name__ == "__main__":
    main()