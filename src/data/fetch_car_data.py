"""
src/data/fetch_car_data.py

Fetches real car telemetry (including DRS status) from OpenF1's car_data
endpoint for a small, targeted selection of races. This endpoint is
high-frequency (~3.7Hz per car), so we only fetch it for a few races,
per driver, to keep the download manageable.

Prerequisite: fetch_openf1.py must have already run, so we can read the
session_key for each target race from the existing *_laps.csv files.

Run from project root:
    python src/data/fetch_car_data.py
"""

import os
import glob
import time
import requests
import pandas as pd

RAW_DIR = "data/raw/openf1"
OUT_DIR = "data/raw/openf1_car_data"
BASE_URL = "https://api.openf1.org/v1"

os.makedirs(OUT_DIR, exist_ok=True)

# Race labels must match the filename prefix used in fetch_openf1.py
# e.g. "2023_bahrain_sakhir_laps.csv" -> "bahrain_sakhir"
TARGET_RACES = [
    "bahrain_sakhir",
    "italy_monza",
    "brazil_interlagos",
]


def get(endpoint, params=None, retries=3, delay=2):
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"    Attempt {attempt+1} failed for {endpoint} ({params}): {e}")
            time.sleep(delay)
    print(f"    Giving up on {endpoint} ({params})")
    return []


def find_session_key_and_drivers(race_label):
    """Read the already-downloaded laps CSV for this race to get session_key + driver list."""
    pattern = os.path.join(RAW_DIR, f"*_{race_label}_laps.csv")
    matches = glob.glob(pattern)
    if not matches:
        print(f"Could not find laps file for race_label={race_label}")
        return None, []
    laps = pd.read_csv(matches[0])
    session_key = laps["session_key"].iloc[0]
    driver_numbers = sorted(laps["driver_number"].unique().tolist())
    return session_key, driver_numbers


def fetch_car_data_for_race(race_label):
    session_key, drivers = find_session_key_and_drivers(race_label)
    if session_key is None:
        return

    print(f"\n=== {race_label} (session_key={session_key}, {len(drivers)} drivers) ===")
    all_data = []

    for driver_number in drivers:
        print(f"  Fetching car_data for driver {driver_number}...")
        data = get(
            "car_data",
            {"session_key": session_key, "driver_number": driver_number},
        )
        if data:
            df = pd.DataFrame(data)
            # Keep only what we need to save space: date, drs, speed
            keep_cols = [c for c in ["date", "driver_number", "drs", "speed"] if c in df.columns]
            df = df[keep_cols]
            all_data.append(df)
        time.sleep(0.5)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined["session_key"] = session_key
        combined["race_label"] = race_label
        out_path = os.path.join(OUT_DIR, f"{race_label}_car_data.csv")
        combined.to_csv(out_path, index=False)
        print(f"  Saved -> {out_path} ({combined.shape})")
    else:
        print(f"  No car_data retrieved for {race_label}")


if __name__ == "__main__":
    for race in TARGET_RACES:
        fetch_car_data_for_race(race)