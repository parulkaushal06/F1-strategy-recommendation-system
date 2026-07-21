"""
Alternative dataset fetcher using Ergast API (more stable than FastF1)

Fetches F1 race results, drivers, constructors, standings, etc.
Ergast is a historical database and very reliable.

Run from project root:
    python src/data/fetch_ergast_data.py
"""

import os
import pandas as pd
import requests
import time

OUT_DIR = "data/raw/ergast"
os.makedirs(OUT_DIR, exist_ok=True)

BASE_URL = "http://ergast.com/api/f1"

def fetch_data(endpoint, year=None, limit=1000):
    """Fetch data from Ergast API with retry logic."""
    for attempt in range(3):
        try:
            if year:
                url = f"{BASE_URL}/{year}/{endpoint}.json?limit={limit}"
            else:
                url = f"{BASE_URL}/{endpoint}.json?limit={limit}"
            
            print(f"Fetching {endpoint}...", end=" ", flush=True)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            print(f"✓ {len(data.get('MRData', {}).get(list(data['MRData'].keys())[0], []))} records")
            return data
        
        except requests.exceptions.RequestException as e:
            print(f"⚠ Error (attempt {attempt+1}/3)")
            if attempt < 2:
                time.sleep(5)
            else:
                print(f"✗ Failed to fetch {endpoint}")
                return None

def flatten_dict(d, parent_key='', sep='_'):
    """Flatten nested JSON."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            if len(v) > 0 and isinstance(v[0], dict):
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)

def fetch_races(year):
    """Fetch races for a given year."""
    data = fetch_data(f"{year}/races")
    if not data:
        return None
    
    races = data['MRData']['RaceTable']['Races']
    df = pd.DataFrame(races)
    
    out_path = os.path.join(OUT_DIR, f"races_{year}.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

def fetch_results(year):
    """Fetch race results for a given year."""
    data = fetch_data(f"{year}/results", limit=10000)
    if not data:
        return None
    
    results = data['MRData']['RaceTable']['Races']
    all_results = []
    
    for race in results:
        race_info = {k: v for k, v in race.items() if k != 'Results'}
        for result in race.get('Results', []):
            merged = {**race_info, **result}
            # Flatten nested data
            merged = flatten_dict(merged)
            all_results.append(merged)
    
    df = pd.DataFrame(all_results)
    out_path = os.path.join(OUT_DIR, f"results_{year}.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

def fetch_drivers():
    """Fetch all drivers."""
    data = fetch_data("drivers", limit=1000)
    if not data:
        return None
    
    drivers = data['MRData']['DriverTable']['Drivers']
    df = pd.DataFrame(drivers)
    
    out_path = os.path.join(OUT_DIR, "drivers.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

def fetch_constructors():
    """Fetch all constructors."""
    data = fetch_data("constructors", limit=1000)
    if not data:
        return None
    
    constructors = data['MRData']['ConstructorTable']['Constructors']
    df = pd.DataFrame(constructors)
    
    out_path = os.path.join(OUT_DIR, "constructors.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

def fetch_driver_standings(year):
    """Fetch driver standings for a given year."""
    data = fetch_data(f"{year}/driverStandings")
    if not data:
        return None
    
    standings = data['MRData']['StandingsTable']['StandingsList']
    if not standings:
        return None
    
    all_standings = []
    for standing in standings:
        for driver_standing in standing.get('DriverStandings', []):
            merged = {**standing, **driver_standing}
            merged = flatten_dict(merged)
            all_standings.append(merged)
    
    df = pd.DataFrame(all_standings)
    out_path = os.path.join(OUT_DIR, f"driver_standings_{year}.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

def fetch_constructor_standings(year):
    """Fetch constructor standings for a given year."""
    data = fetch_data(f"{year}/constructorStandings")
    if not data:
        return None
    
    standings = data['MRData']['StandingsTable']['StandingsList']
    if not standings:
        return None
    
    all_standings = []
    for standing in standings:
        for constructor_standing in standing.get('ConstructorStandings', []):
            merged = {**standing, **constructor_standing}
            merged = flatten_dict(merged)
            all_standings.append(merged)
    
    df = pd.DataFrame(all_standings)
    out_path = os.path.join(OUT_DIR, f"constructor_standings_{year}.csv")
    df.to_csv(out_path, index=False)
    print(f"  → Saved {out_path}")
    return df

if __name__ == "__main__":
    print("="*60)
    print("Fetching F1 Data from Ergast API (Reliable)")
    print("="*60)
    
    # Fetch global data (drivers, constructors)
    print("\n[1] Drivers & Constructors")
    fetch_drivers()
    fetch_constructors()
    
    # Fetch season data
    print("\n[2] 2023 Season Data")
    year = 2023
    fetch_races(year)
    fetch_results(year)
    fetch_driver_standings(year)
    fetch_constructor_standings(year)
    
    print("\n✓ Done! Check data/raw/ergast/")
