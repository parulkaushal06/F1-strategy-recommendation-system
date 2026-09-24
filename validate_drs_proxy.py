"""
validate_drs_proxy.py

Validates drs_zone_proxy (our rule-based guess: gap_to_ahead_ms <= 1000)
against REAL DRS telemetry from OpenF1's car_data endpoint, for the 2 races
where we have it (Bahrain, Brazil/Interlagos -- see docs/06_known_limitations.md,
which incorrectly said 3 races including Monza; only 2 car_data files actually
exist, this should be corrected).

Real DRS codes (confirmed via OpenF1 docs + FastF1 + community sources):
  0, 1        = DRS off
  8           = Detected, eligible (in a DRS zone, gap < 1s, but not activated)
  10, 12, 14  = DRS actually ON (activated)
  2, 3, 9, 13 = rare/unclear transition states (<0.1% of readings, ignored)

Our proxy predicts ELIGIBILITY (gap < 1s), which is conceptually closer to
"eligible or on" (8/10/12/14) than to "actually on" (10/12/14) -- a driver
can be eligible without choosing to activate DRS that exact instant. This
script reports BOTH comparisons so the difference is honest and visible,
not picked to make the proxy look better than it is.

Run from project root:
    python validate_drs_proxy.py
"""
import glob
import os
import sys

import pandas as pd

sys.path.insert(0, ".")
from src.data.final_merge import build_driver_map

CAR_DATA_DIR = "data/raw/openf1_car_data"
LAPS_DIR = "data/raw/openf1"
CLEANED_PATH = "data/processed/cleaned_dataset.csv"

REAL_ON = {10, 12, 14}
REAL_ELIGIBLE_OR_ON = {8, 10, 12, 14}


def load_laps_timing():
    """All *_laps.csv concatenated -- gives (session_key, driver_number,
    lap_number, date_start) so we know which lap each telemetry ping belongs to."""
    files = glob.glob(os.path.join(LAPS_DIR, "*_laps.csv"))
    if not files:
        raise FileNotFoundError(
            f"No lap timing files found in {LAPS_DIR}. Need date_start per lap "
            f"to bucket car_data readings into laps -- check fetch_openf1.py ran."
        )
    laps = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    laps["date_start"] = pd.to_datetime(laps["date_start"], errors="coerce")
    return laps.dropna(subset=["date_start"])


def bucket_telemetry_into_laps(car_data: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    """
    For each (session_key, driver_number), assign every high-frequency car_data
    reading to the lap it happened during, using merge_asof (backward): the
    telemetry's timestamp is matched to the most recent lap start <= that time.
    """
    car_data = car_data.copy()
    car_data["date"] = pd.to_datetime(car_data["date"], errors="coerce")
    car_data = car_data.dropna(subset=["date"])

    session_keys = car_data["session_key"].unique()
    laps_session = laps[laps["session_key"].isin(session_keys)]

    results = []
    for (session_key, driver_number), group in car_data.groupby(["session_key", "driver_number"]):
        driver_laps = laps_session[
            (laps_session["session_key"] == session_key)
            & (laps_session["driver_number"] == driver_number)
        ].sort_values("date_start")
        if driver_laps.empty:
            continue
        g = group.sort_values("date")
        matched = pd.merge_asof(
            g, driver_laps[["date_start", "lap_number"]],
            left_on="date", right_on="date_start", direction="backward",
        )
        results.append(matched)

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True).copy()


def summarize_per_lap(bucketed: pd.DataFrame) -> pd.DataFrame:
    """One row per (session_key, driver_number, lap_number): did DRS reach
    'eligible or on' / 'actually on' at ANY point during that lap."""
    bucketed = bucketed.dropna(subset=["lap_number"])
    bucketed["real_eligible_or_on"] = bucketed["drs"].isin(REAL_ELIGIBLE_OR_ON)
    bucketed["real_on"] = bucketed["drs"].isin(REAL_ON)

    return bucketed.groupby(["session_key", "driver_number", "lap_number"]).agg(
        real_eligible_or_on=("real_eligible_or_on", "any"),
        real_on=("real_on", "any"),
    ).reset_index()


def report_agreement(merged: pd.DataFrame, real_col: str, label: str):
    proxy = merged["drs_zone_proxy"].astype(bool)
    real = merged[real_col].astype(bool)

    agree = (proxy == real).mean() * 100
    # Recall: of laps where DRS was really eligible/on, how often did our proxy say yes?
    recall = (proxy & real).sum() / max(real.sum(), 1) * 100
    # False positive rate: of laps where DRS was NOT really eligible/on, how often did our proxy wrongly say yes?
    fpr = (proxy & ~real).sum() / max((~real).sum(), 1) * 100

    print(f"\n=== Proxy vs '{label}' (n={len(merged)}) ===")
    print(f"Overall agreement: {agree:.1f}%")
    print(f"Recall (caught real DRS when it happened): {recall:.1f}%")
    print(f"False positive rate (said yes when it wasn't): {fpr:.1f}%")


def main():
    print("Loading raw car_data files...")
    car_data_files = glob.glob(os.path.join(CAR_DATA_DIR, "*_car_data.csv"))
    if not car_data_files:
        print(f"No car_data files found in {CAR_DATA_DIR}")
        return
    car_data = pd.concat([pd.read_csv(f) for f in car_data_files], ignore_index=True)
    print(f"  {len(car_data)} telemetry readings across {car_data['race_label'].unique()}")

    print("Loading lap timing (date_start per lap)...")
    laps = load_laps_timing()

    print("Bucketing high-frequency telemetry into laps (this takes a minute)...")
    bucketed = bucket_telemetry_into_laps(car_data, laps)
    if bucketed.empty:
        print("Nothing matched -- check session_key overlap between car_data and laps files.")
        return

    per_lap_real = summarize_per_lap(bucketed)
    print(f"  {len(per_lap_real)} (driver, lap) rows with real DRS ground truth")

    print("\nMapping driver_number -> driverId...")
    driver_map = build_driver_map()
    per_lap_real = per_lap_real.merge(driver_map, on="driver_number", how="left")
    unmatched = per_lap_real["driverId"].isna().sum()
    if unmatched:
        print(f"  WARNING: {unmatched} rows had no driverId match, dropping them")
    per_lap_real = per_lap_real.dropna(subset=["driverId"])
    per_lap_real["driverId"] = per_lap_real["driverId"].astype(int)

    print("Loading cleaned_dataset.csv for raceId + drs_zone_proxy...")
    df = pd.read_csv(CLEANED_PATH, low_memory=False)

    # Bahrain and Brazil/Interlagos, 2023 -- the only 2 races with real car_data.
    target_circuits = ["Bahrain International Circuit", "Autódromo José Carlos Pace"]
    scoped = df[(df["year"] == 2023) & (df["circuit_name"].isin(target_circuits))]
    race_id_map = scoped[["raceId", "circuit_name"]].drop_duplicates()
    print(f"  Matched races: {race_id_map.to_dict('records')}")

    # session_key -> raceId: since car_data.race_label directly tells us which
    # of the 2 races each session_key belongs to, use that instead of rebuilding
    # the full Ergast<->OpenF1 session mapping just for 2 races.
    session_to_circuit = {"bahrain_sakhir": "Bahrain International Circuit",
                           "brazil_interlagos": "Autódromo José Carlos Pace"}
    car_data_race_label = car_data[["session_key", "race_label"]].drop_duplicates()
    car_data_race_label["circuit_name"] = car_data_race_label["race_label"].map(session_to_circuit)
    session_to_race = car_data_race_label.merge(race_id_map, on="circuit_name", how="left")

    per_lap_real = per_lap_real.merge(
        session_to_race[["session_key", "raceId"]], on="session_key", how="left"
    )
    per_lap_real = per_lap_real.dropna(subset=["raceId"])
    per_lap_real["raceId"] = per_lap_real["raceId"].astype(int)
    per_lap_real = per_lap_real.rename(columns={"lap_number": "lap"})

    merged = per_lap_real.merge(
        df[["raceId", "driverId", "lap", "drs_zone_proxy"]],
        on=["raceId", "driverId", "lap"], how="inner",
    )
    print(f"\nFinal matched rows for comparison: {len(merged)}")

    if merged.empty:
        print("No rows matched -- something in the ID bridging didn't line up.")
        return

    report_agreement(merged, "real_eligible_or_on", "eligible or on (DRS code 8/10/12/14)")
    report_agreement(merged, "real_on", "actually on (DRS code 10/12/14)")


if __name__ == "__main__":
    main()