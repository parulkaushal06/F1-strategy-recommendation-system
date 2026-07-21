# Data Sources

This project combines **two independent data sources** because no single public source
covers both (a) full historical race results and (b) detailed car telemetry.

## Source 1: Ergast / Kaggle — "Formula 1 World Championship (1950–2024)"

- **What it is**: A relational dataset of official F1 results — the "results ledger."
  Originally served by the Ergast API (now deprecated), mirrored and kept updated on
  Kaggle by user Vopani (Rohan Rao).
- **Coverage**: 1950–2024, all seasons, all races.
- **Granularity caveat**: lap-by-lap timing data (`lap_times.csv`) is only reliable from
  **2011 onward** — earlier seasons weren't timed at that resolution. This project filters
  to `year >= 2011` during feature engineering for this reason.
- **Files used**: `races.csv`, `results.csv`, `drivers.csv`, `constructors.csv`,
  `circuits.csv`, `lap_times.csv`, `pit_stops.csv`, `qualifying.csv`, `status.csv`.
- **What it provides**: final race results, finishing position, points, pit stop counts,
  lap times, qualifying grid position, driver/constructor/circuit metadata.
- **What it does NOT provide**: tire compound, DRS status, weather, speed telemetry.

## Source 2: OpenF1 API

- **What it is**: A free, public REST API providing real F1 telemetry — no API key
  required. (`https://openf1.org`)
- **Coverage**: **2023 onward only.** This is a hard limit of the source itself — OpenF1
  does not have historical data before 2023.
- **Endpoints used**:
  - `/sessions` — race session metadata (session_key, circuit, date)
  - `/laps` — lap times, sector times, speed trap readings
  - `/pit` — real pit stop events and durations
  - `/stints` — tire compound and stint length per driver
  - `/weather` — track/air temperature, rainfall, wind, humidity
  - `/drivers` — driver_number to name/team mapping
  - `/car_data` — high-frequency (~3.7Hz) telemetry including **real DRS status**,
    fetched only for 3 selected races (see below) due to its size
- **What it provides that Ergast can't**: real tire compound, real DRS activation
  status, weather, granular speed telemetry.

## Why not FastF1 (the Python library)?

FastF1 was the original plan for telemetry, since it wraps the same underlying F1 timing
data. In practice, it repeatedly failed in this project's environment with
`SessionNotAvailableError`-style errors that couldn't be reliably resolved (network/
environment issue, not a data problem). OpenF1 was used instead as a more reliable,
lightweight REST alternative — this is a legitimate engineering substitution, documented
here rather than hidden.

## Why DRS validation only covers 3 races, not the full season

OpenF1's `car_data` endpoint is per-car, high-frequency telemetry — a full season would be
tens of millions of rows. Instead, `car_data` was fetched for **3 high-overtaking races**
(Bahrain, Italy/Monza, Brazil/Interlagos) specifically to validate the project's rule-based
DRS proxy (`gap_to_ahead_ms <= 1000`, i.e. within 1 second of the car ahead) against real
DRS activation data, rather than to power the main model.

## Summary table

| | Ergast/Kaggle | OpenF1 |
|---|---|---|
| Years covered | 1950–2024 (lap data reliable from 2011) | 2023 only |
| Race results | ✅ | — |
| Pit stops | ✅ | ✅ (validated against Ergast, 100% agreement — see `04_data_cleaning.md`) |
| Tire compound | ❌ (proxy only) | ✅ real |
| DRS status | ❌ (proxy only) | ✅ real (3 races only, via `car_data`) |
| Weather | ❌ | ✅ |
| Real ERS deployment mode | ❌ — not public anywhere | ❌ — not public anywhere |

**Note on ERS**: no public data source, including OpenF1, exposes real ERS (Energy
Recovery System) deployment mode — this is proprietary team telemetry that F1 teams do
not release. Any "ERS Overtake Mode" recommendation this project produces is a proxy
inferred from throttle/speed patterns, not ground-truth team data. This is stated clearly
here and in the dashboard output.