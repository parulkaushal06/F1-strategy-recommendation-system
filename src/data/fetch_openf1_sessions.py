"""
src/data/fetch_openf1_sessions.py

Saves session metadata (session_key -> circuit_short_name, country_name, etc.)
for 2023 races. This is needed by final_merge.py to map OpenF1 session_key
to Ergast raceId via circuit name.

Run from project root:
    python src/data/fetch_openf1_sessions.py
"""

import os
import requests
import pandas as pd

OUT_DIR = "data/raw/openf1"
BASE_URL = "https://api.openf1.org/v1"

os.makedirs(OUT_DIR, exist_ok=True)


def main(year=2023):
    resp = requests.get(
        f"{BASE_URL}/sessions", params={"year": year, "session_type": "Race"}, timeout=30
    )
    resp.raise_for_status()
    sessions = pd.DataFrame(resp.json())

    out_path = os.path.join(OUT_DIR, f"{year}_sessions.csv")
    sessions.to_csv(out_path, index=False)
    print(f"Saved -> {out_path} ({sessions.shape})")
    print(sessions[["session_key", "circuit_short_name", "country_name", "location"]])


if __name__ == "__main__":
    main(2023)