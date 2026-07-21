"""
src/data/retry_failed_races.py

Retry fetching specific races that failed in the main fetch_fastf1.py run.
Edit FAILED_RACES below with whatever printed as "Failed for ..." in your run.
"""

import time
from data.fetch_openf1 import fetch_race  # reuse the same function

FAILED_RACES = [
    (2023, "Abu Dhabi Grand Prix"),
    # add more (year, race_name) tuples here if others failed too
]

if __name__ == "__main__":
    for year, race_name in FAILED_RACES:
        print(f"Retrying {year} {race_name}...")
        time.sleep(2)  # small delay helps with transient API issues
        fetch_race(year, race_name)