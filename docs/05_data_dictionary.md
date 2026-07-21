# Data Dictionary

Every column in `data/processed/final_merged_dataset.csv` (post-cleaning, 64 columns),
grouped by category. "Source" indicates where the raw value came from; "Derived" means
it was calculated during the pipeline.

## Identifiers

| Column | Type | Meaning | Source |
|---|---|---|---|
| `raceId` | int | Unique race ID | Ergast |
| `driverId` | int | Unique driver ID | Ergast |
| `driverRef` | text | Driver reference name (e.g. "vettel") | Ergast |
| `code` | text | 3-letter driver code (e.g. "VET") | Ergast |
| `lap` | int | Lap number within the race | Ergast |
| `driver_number` | float | OpenF1's driver number (2023 rows only) | OpenF1 |
| `session_key` | float | OpenF1 session ID (2023 rows only) | OpenF1 |
| `meeting_key` | float | OpenF1 race weekend ID (2023 rows only) | OpenF1 |

## Race context

| Column | Type | Meaning | Source |
|---|---|---|---|
| `year`, `round` | int | Season year, round number | Ergast |
| `circuit_name`, `location`, `country` | text | Race location details | Ergast |
| `date` | text | Race date | Ergast |
| `constructor_name` | text | Team name | Ergast |
| `total_laps` | int | Total laps in this race | Derived |

## Position & timing

| Column | Type | Meaning | Source |
|---|---|---|---|
| `position` | int | Running position at this lap | Ergast |
| `grid` | int | Starting grid position (0 = pit lane start) | Ergast |
| `milliseconds` | int | This lap's time, in ms | Ergast |
| `cum_time_ms` | int | Cumulative race time up to this lap | Derived |
| `gap_to_leader_ms` / `gap_to_leader_s` | int/float | Gap to race leader | Derived |
| `gap_to_ahead_ms` | float | Gap to the car directly ahead | Derived |
| `gap_per_lap_covered_s` | float | Gap normalized by laps completed | Derived |
| `race_progress` | float | `lap / total_laps`, range 0–1 | Derived |
| `position_vs_grid` | int | Places gained (+) or lost (-) vs. start | Derived |
| `position_change` | int | Position change vs. previous lap | Derived |
| `rolling_lap_time_ms` | float | 3-lap rolling average pace | Derived |
| `pace_delta_to_fastest_ms` | float | Gap to the fastest lap set that round | Derived |

## Pit stops & tires

| Column | Type | Meaning | Source |
|---|---|---|---|
| `pit_stop_this_lap` | int (0/1) | Pit stop happened this lap | Ergast (validated 100% against OpenF1 — see `04_data_cleaning.md`) |
| `cumulative_pit_stops` | int | Running pit-stop count | Derived |
| `laps_since_last_pit` | int | Tire-age proxy | Derived |
| `pit_duration_ms` | float | Pit stop duration (Ergast) | Ergast |
| `pit_stop_duration_s` | float | Pit stop duration (OpenF1, 2023 only) | OpenF1 |
| `tire_age_ratio` | float | `laps_since_last_pit / total_laps` | Derived |
| `compound` | text | **Real** tire compound — SOFT/MEDIUM/HARD (2023 only) | OpenF1 |
| `stint_number` | float | Which tire stint this lap belongs to (2023 only) | OpenF1 |
| `tyre_age_at_stint_start` | float | Tire age when this stint began (2023 only) | OpenF1 |
| `drs_zone_proxy` | int (0/1) | **Rule-based estimate**: within 1s of car ahead | Derived (proxy — see `06_known_limitations.md`) |
| `pit_window_proxy` | int (0/1) | **Rule-based estimate**: tire age 15–30 laps | Derived (proxy) |

## OpenF1 telemetry (2023 only)

| Column | Meaning |
|---|---|
| `duration_sector_1/2/3` | Real sector times |
| `i1_speed`, `i2_speed`, `st_speed` | Speed trap readings (intermediate 1/2, start-finish) |
| `is_pit_out_lap` | 1 if this lap is the out-lap right after a pit stop |
| `lap_duration` | OpenF1's own lap time (redundant with `milliseconds`, kept for cross-checking) |
| `segments_sector_1/2/3` | Mini-sector performance flags |
| `date_start`, `date_openf1` | Timestamps for this lap / weather reading |

## Weather (2023 only)

| Column | Meaning |
|---|---|
| `air_temperature`, `track_temperature` | °C |
| `rainfall` | Rainfall indicator |
| `humidity` | % |
| `pressure` | Air pressure |
| `wind_speed`, `wind_direction` | Wind conditions |

## Outcome / label

| Column | Type | Meaning | Source |
|---|---|---|---|
| `statusId` | int | Finish status code (1 = Finished, others = DNF reasons) | Ergast |
| `points` | float | Championship points earned | Ergast |
| `positionOrder` | int | Official final classification | Ergast |
| `won` | int (0/1) | **Model target label** — 1 if this driver won the race | Derived |
| `has_openf1_telemetry` | int (0/1) | 1 if this row has real OpenF1 data attached | Derived (added during cleaning) |