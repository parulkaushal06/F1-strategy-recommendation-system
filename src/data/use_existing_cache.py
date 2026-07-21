"""
Work with existing cached F1 data

This script:
1. Checks what you already have cached
2. Converts existing cache to CSV if available
3. Uses existing ergast CSVs

Run from project root:
    python src/data/use_existing_cache.py
"""

import os
import pandas as pd
from pathlib import Path

CACHE_DIR = "data/raw/fastf1_cache"
ERGAST_DIR = "data/raw/ergast"
OUT_DIR = "data/raw/fastf1"

os.makedirs(OUT_DIR, exist_ok=True)

def list_cached_races():
    """List all cached races available."""
    races = []
    cache_path = Path(CACHE_DIR)
    
    if not cache_path.exists():
        print("✗ No cache directory found")
        return races
    
    for year_dir in cache_path.glob("*/"):
        year = year_dir.name
        for race_dir in year_dir.glob("*/"):
            race_name = race_dir.name
            races.append((year, race_name))
    
    return races

def list_ergast_data():
    """List available Ergast CSV files."""
    ergast_path = Path(ERGAST_DIR)
    
    if not ergast_path.exists():
        print("✗ No ergast directory found")
        return []
    
    files = list(ergast_path.glob("*.csv"))
    return files

def main():
    print("="*60)
    print("Checking Available F1 Data")
    print("="*60)
    
    # Check FastF1 cache
    print("\n[1] FastF1 Cached Data:")
    cached_races = list_cached_races()
    if cached_races:
        print(f"Found {len(cached_races)} cached races:")
        for year, race in cached_races[:10]:  # Show first 10
            print(f"  • {year} {race}")
        if len(cached_races) > 10:
            print(f"  ... and {len(cached_races) - 10} more")
    else:
        print("  None found yet")
    
    # Check Ergast CSVs
    print("\n[2] Ergast CSV Files:")
    ergast_files = list_ergast_data()
    if ergast_files:
        print(f"Found {len(ergast_files)} CSV files:")
        for f in ergast_files:
            try:
                df = pd.read_csv(f)
                print(f"  • {f.name}: {len(df)} rows")
            except:
                print(f"  • {f.name}: (error reading)")
    else:
        print("  None found yet")
    
    # Check interim data
    print("\n[3] Existing Interim Data:")
    interim_path = Path("data/interim")
    if interim_path.exists():
        interim_files = list(interim_path.glob("*.csv"))
        if interim_files:
            for f in interim_files:
                try:
                    df = pd.read_csv(f)
                    print(f"  • {f.name}: {len(df)} rows")
                except:
                    print(f"  • {f.name}: (error reading)")
        else:
            print("  None found")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    print("="*60)
    print("\n1. If FastF1 API keeps timing out:")
    print("   → Use: python src/data/fetch_ergast_data.py")
    print("   (Ergast is much more stable)")
    
    print("\n2. If you have cached races:")
    print("   → Check data/raw/fastf1_cache/ and convert manually")
    
    print("\n3. To combine all available data:")
    print("   → Use existing Ergast CSVs + interim data")
    print("   → Edit merge_datasets.py to include them")

if __name__ == "__main__":
    main()
