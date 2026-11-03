"""
src/data/consolidate_openf1.py

Combines all per-race OpenF1 CSVs (laps, pits, stints, weather, drivers)
downloaded by fetch_openf1.py / fetch_openf1_drivers.py into a single
unified per-lap table.

Run from project root, after fetch_openf1.py and fetch_openf1_drivers.py
have both completed:
    python src/data/consolidate_openf1.py
"""

import os
import glob
import pandas as pd

RAW_DIR = "data/raw/openf1"
INTERIM_DIR = "data/interim"

os.makedirs(INTERIM_DIR, exist_ok=True)


def load_and_concat(pattern):
    """Load all CSVs matching a glob pattern and concatenate them."""
    files = glob.glob(os.path.join(RAW_DIR, pattern))
    if not files:
        print(f"No files found for pattern: {pattern}")
        return pd.DataFrame()
    dfs = [pd.read_csv(f) for f in files]
    combined = pd.concat(dfs, ignore_index=True)
    print(f"{pattern}: {len(files)} files -> {combined.shape}")
    return combined


def expand_stints_to_laps(stints):
    """
    stints.csv has one row per stint: lap_start, lap_end, compound, driver_number,
    session_key. Expand this into one row per (session_key, driver_number, lap_number)
    so it can be joined onto the laps table directly.
    """
    # Drop stints with missing lap boundaries — can't expand these into lap rows.
    before = len(stints)
    stints = stints.dropna(subset=["lap_start", "lap_end"]).copy()
    dropped = before - len(stints)
    if dropped:
        print(f"  Skipped {dropped} stint rows with missing lap_start/lap_end")

    rows = []
    for _, s in stints.iterrows():
        for lap_num in range(int(s["lap_start"]), int(s["lap_end"]) + 1):
            rows.append({
                "session_key": s["session_key"],
                "driver_number": s["driver_number"],
                "lap_number": lap_num,
                "compound": s.get("compound"),
                "stint_number": s.get("stint_number"),
                "tyre_age_at_stint_start": s.get("tyre_age_at_start"),
            })
    result = pd.DataFrame(rows)
    # BUGFIX: consecutive stints can share a boundary lap (stint 1 ends lap 4, stint 2
    # starts lap 4), creating two compound values for the same lap. Keep the later
    # stint's value for that lap — the pit stop completed during that lap, so the new
    # tire is the more meaningful state for the rest of that lap.
    result = result.sort_values(["session_key", "driver_number", "lap_number", "stint_number"])
    result = result.drop_duplicates(subset=["session_key", "driver_number", "lap_number"], keep="last")
    return result


def main():
    laps = load_and_concat("*_laps.csv")
    pits = load_and_concat("*_pits.csv")
    stints = load_and_concat("*_stints.csv")
    weather = load_and_concat("*_weather.csv")

    drivers_path = os.path.join(RAW_DIR, "2023_drivers_mapping.csv")
    if os.path.exists(drivers_path):
        drivers = pd.read_csv(drivers_path)
        print(f"drivers mapping -> {drivers.shape}")
    else:
        print("WARNING: drivers mapping file not found. Run fetch_openf1_drivers.py first.")
        drivers = pd.DataFrame()

    if laps.empty:
        print("No laps data found — nothing to consolidate.")
        return

    df = laps.copy()

    # ---- Pit stops: mark which lap had an actual pit stop + its duration ----
    if not pits.empty:
        pits_slim = pits[["session_key", "driver_number", "lap_number", "pit_duration"]].rename(
            columns={"pit_duration": "pit_stop_duration_s"}
        )
        pits_slim["pit_stop_this_lap"] = 1
        df = df.merge(
            pits_slim, on=["session_key", "driver_number", "lap_number"], how="left"
        )
        df["pit_stop_this_lap"] = df["pit_stop_this_lap"].fillna(0).astype(int)
        df["pit_stop_duration_s"] = df["pit_stop_duration_s"].fillna(0)
    else:
        df["pit_stop_this_lap"] = 0
        df["pit_stop_duration_s"] = 0.0

    # ---- Tire compound: expand stints to per-lap and join ----
    if not stints.empty:
        stint_laps = expand_stints_to_laps(stints)
        df = df.merge(
            stint_laps, on=["session_key", "driver_number", "lap_number"], how="left"
        )

    # ---- Weather: nearest-time join per session ----
    if not weather.empty and "date_start" in df.columns:
        df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
        weather["date"] = pd.to_datetime(weather["date"], errors="coerce")

        # merge_asof can't handle nulls in the join key — split those rows out,
        # merge weather only onto rows with a valid date_start, then recombine.
        has_date = df["date_start"].notna()
        df_valid = df[has_date].copy()
        df_invalid = df[~has_date].copy()
        if len(df_invalid):
            print(f"  {len(df_invalid)} rows have missing/invalid date_start — "
                  f"skipping weather join for these")

        merged_chunks = []
        for session_key, group in df_valid.groupby("session_key"):
            w = weather[weather["session_key"] == session_key].dropna(subset=["date"]).sort_values("date")
            if w.empty:
                merged_chunks.append(group)
                continue
            g = group.sort_values("date_start")
            merged = pd.merge_asof(
                g, w, left_on="date_start", right_on="date", direction="nearest"
            )
            merged_chunks.append(merged)
        df_valid_merged = pd.concat(merged_chunks, ignore_index=True) if merged_chunks else df_valid
        df = pd.concat([df_valid_merged, df_invalid], ignore_index=True)

        # BUGFIX: the merge_asof above creates session_key_x/session_key_y for rows
        # that went through it, while rows that skipped it kept plain session_key.
        # The driver-name merge below relies on session_key — coalesce it back into
        # one clean column NOW, before that merge runs, or the driver merge will
        # silently fail for the majority of rows (exactly the bug this comment is here
        # to prevent from reappearing).
        for base_col in ["session_key", "meeting_key"]:
            suffixed = [c for c in [f"{base_col}_x", f"{base_col}_y"] if c in df.columns]
            if suffixed:
                if base_col not in df.columns:
                    df[base_col] = pd.NA
                for c in suffixed:
                    df[base_col] = df[base_col].combine_first(df[c])
                df = df.drop(columns=suffixed)
        print(f"  After coalescing post-weather-merge: "
              f"{df['session_key'].notna().sum()} rows have a usable session_key")

    # ---- Driver info: name, team ----
    if not drivers.empty:
        drivers_slim = drivers[
            ["session_key", "driver_number", "full_name", "name_acronym", "team_name"]
        ].drop_duplicates()
        df = df.merge(drivers_slim, on=["session_key", "driver_number"], how="left")

    out_path = os.path.join(INTERIM_DIR, "openf1_lap_level.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSaved consolidated OpenF1 dataset -> {out_path}")
    print(f"Shape: {df.shape}")
    print(df.columns.tolist())
    print(df.head())


if __name__ == "__main__":
    main()