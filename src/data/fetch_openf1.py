"""
src/data/fetch_openf1.py

Downloads session, lap, pit, stint, and weather data from the OpenF1 API
(https://openf1.org) for a given season. No API key required.

OpenF1 gives real DRS status and tire compound data (not proxies), covering
2023 onwards.

Run from project root:
    python src/data/fetch_openf1.py
"""

import os
import time
import requests
import pandas as pd

OUT_DIR = "data/raw/openf1"
BASE_URL = "https://api.openf1.org/v1"

os.makedirs(OUT_DIR, exist_ok=True)


def get(endpoint, params=None, retries=3, delay=2):
    """GET request with basic retry logic."""
    for attempt in range(retries):
        try:
            resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {endpoint} ({params}): {e}")
            time.sleep(delay)
    print(f"  Giving up on {endpoint} ({params})")
    return []


def get_race_sessions(year):
    """Get all Race sessions for a given year."""
    data = get("sessions", {"year": year, "session_type": "Race"})
    return pd.DataFrame(data)


def fetch_session_data(session_key, race_label, year):
    """Fetch laps, pit stops, stints, and weather for one session."""
    print(f"Fetching {year} {race_label} (session_key={session_key})...")

    laps = pd.DataFrame(get("laps", {"session_key": session_key}))
    pits = pd.DataFrame(get("pit", {"session_key": session_key}))
    stints = pd.DataFrame(get("stints", {"session_key": session_key}))
    weather = pd.DataFrame(get("weather", {"session_key": session_key}))

    safe_name = str(race_label).replace(" ", "_").lower()

    if not laps.empty:
        laps.to_csv(os.path.join(OUT_DIR, f"{year}_{safe_name}_laps.csv"), index=False)
    if not pits.empty:
        pits.to_csv(os.path.join(OUT_DIR, f"{year}_{safe_name}_pits.csv"), index=False)
    if not stints.empty:
        stints.to_csv(os.path.join(OUT_DIR, f"{year}_{safe_name}_stints.csv"), index=False)
    if not weather.empty:
        weather.to_csv(os.path.join(OUT_DIR, f"{year}_{safe_name}_weather.csv"), index=False)

    print(
        f"  -> laps={laps.shape}, pits={pits.shape}, "
        f"stints={stints.shape}, weather={weather.shape}"
    )
    time.sleep(1)  # be polite to the free API


def fetch_season(year):
    sessions = get_race_sessions(year)
    if sessions.empty:
        print(f"No race sessions found for {year}")
        return

    print(f"Found {len(sessions)} race sessions for {year}")
    for _, row in sessions.iterrows():
        race_label = f"{row.get('country_name', 'unknown')}_{row.get('circuit_short_name', row['session_key'])}"
        fetch_session_data(row["session_key"], race_label, year)


if __name__ == "__main__":
    # Start with one season first
    SEASONS_TO_FETCH = [2023]

    for yr in SEASONS_TO_FETCH:
        fetch_season(yr)