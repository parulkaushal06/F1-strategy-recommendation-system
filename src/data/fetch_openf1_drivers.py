"""
src/data/fetch_openf1_drivers.py

Fetches the driver_number -> driver name/team mapping for every 2023 race
session from OpenF1. Needed to join OpenF1 data (keyed by driver_number)
with Ergast data (keyed by driverId/driverRef).

Run from project root:
    python src/data/fetch_openf1_drivers.py
"""

import os
import time
import requests
import pandas as pd

OUT_DIR = "data/raw/openf1"
BASE_URL = "https://api.openf1.org/v1"

os.makedirs(OUT_DIR, exist_ok=True)


def get(endpoint, params=None, retries=3, delay=2):
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {endpoint} ({params}): {e}")
            time.sleep(delay)
    return []


def fetch_all_drivers(year=2023):
    sessions = pd.DataFrame(get("sessions", {"year": year, "session_type": "Race"}))
    all_drivers = []

    for _, row in sessions.iterrows():
        session_key = row["session_key"]
        label = f"{row.get('country_name','unknown')}_{row.get('circuit_short_name', session_key)}"
        print(f"Fetching drivers for {year} {label} (session_key={session_key})...")
        drivers = pd.DataFrame(get("drivers", {"session_key": session_key}))
        if not drivers.empty:
            drivers["year"] = year
            drivers["race_label"] = label
            all_drivers.append(drivers)
        time.sleep(1)

    if all_drivers:
        combined = pd.concat(all_drivers, ignore_index=True)
        out_path = os.path.join(OUT_DIR, f"{year}_drivers_mapping.csv")
        combined.to_csv(out_path, index=False)
        print(f"\nSaved -> {out_path} ({combined.shape})")
        print(combined.columns.tolist())
    else:
        print("No driver data fetched.")


if __name__ == "__main__":
    fetch_all_drivers(2023)