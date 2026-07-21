# Data Collection

This document lists the exact scripts run, in order, to collect all raw data.
All scripts live in `src/data/` and are run from the project root.

## Step 1 — Download Ergast/Kaggle base dataset

Downloaded manually from Kaggle: "Formula 1 World Championship (1950–2024)" by Vopani.
14 CSV files placed in `data/raw/ergast/`:
`circuits.csv`, `constructor_results.csv`, `constructor_standings.csv`,
`constructors.csv`, `driver_standings.csv`, `drivers.csv`, `lap_times.csv`,
`pit_stops.csv`, `qualifying.csv`, `races.csv`, `results.csv`, `seasons.csv`,
`sprint_results.csv`, `status.csv`.

## Step 2 — Fetch OpenF1 session-level data (2023 season)

```bash
python src/data/fetch_openf1.py
```

Fetches `laps`, `pit`, `stints`, and `weather` for every 2023 Race session.
Output: `data/raw/openf1/{year}_{country}_{circuit}_{laps|pits|stints|weather}.csv`
(one set of 4 files per race, ~22 races).

## Step 3 — Fetch OpenF1 driver mapping

```bash
python src/data/fetch_openf1_drivers.py
```

Fetches `driver_number -> full_name, name_acronym, team_name` for every 2023 session.
Needed because OpenF1 identifies drivers by `driver_number`, while Ergast uses
`driverId`/`code`. Output: `data/raw/openf1/2023_drivers_mapping.csv`.

## Step 4 — Fetch OpenF1 session metadata

```bash
python src/data/fetch_openf1_sessions.py
```

Fetches `session_key -> circuit_short_name, country_name` for every 2023 Race session.
Needed to bridge OpenF1's `session_key` to Ergast's `raceId` via circuit name matching.
Output: `data/raw/openf1/2023_sessions.csv`.

## Step 5 — Fetch real DRS telemetry for validation (3 races only)

```bash
python src/data/fetch_car_data.py
```

Fetches high-frequency `car_data` (including real DRS status) for Bahrain, Italy (Monza),
and Brazil (Interlagos) — see `01_data_sources.md` for why only 3 races. Output:
`data/raw/openf1_car_data/{race}_car_data.csv`.

## Known collection issues and how they were resolved

| Issue | Cause | Resolution |
|---|---|---|
| FastF1 repeatedly failed with load errors | Environment/network instability with FastF1's timing data source | Switched to OpenF1 REST API instead |
| `KeyError: 'meeting_name'` on first OpenF1 attempt | Assumed field name that doesn't exist in the `/sessions` response | Rebuilt race label from `country_name` + `circuit_short_name` instead |
| Some `/pit` requests failed after retries for isolated sessions | Transient OpenF1 API issue | Script continues past individual failures; missing pit data for a handful of laps is acceptable at this scale |