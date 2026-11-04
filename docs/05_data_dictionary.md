# Cleaned dataset dictionary

The schema below is the 66-column header in the current local `data/processed/cleaned_dataset.csv`. Source snapshots can change; inspect the CSV header and `src/data/clean_data.py` after rebuilding. `models/feature_columns.pkl` is the authoritative ordered model input list.

## Identity and race context

| Columns | Meaning |
|---|---|
| `raceId`, `driverId` | Ergast race and driver identifiers |
| `driverRef`, `code` | Ergast driver reference and 3-letter code |
| `year`, `round`, `date` | Season, championship round, and race date |
| `circuit_name`, `location`, `country` | Circuit and event location labels |
| `constructor_name` | Ergast constructor/team label |
| `lap`, `total_laps` | Current lap and race distance |
| `driver_number`, `session_key`, `meeting_key` | OpenF1 identity values; nullable outside matched enrichment |

## Position, timing, and derived race state

| Columns | Meaning |
|---|---|
| `position`, `grid` | Running position and starting grid position |
| `milliseconds` | Lap time in milliseconds from the historical timing table |
| `cum_time_ms` | Cumulative lap time used to derive race gaps |
| `gap_to_leader_ms`, `gap_to_leader_s` | Gap to leader in milliseconds and seconds (duplicate units) |
| `gap_to_ahead_ms` | Gap from the immediately preceding position in the lap order; leader value is an artifact, not a real gap |
| `gap_per_lap_covered_s` | Gap to leader normalized by laps completed |
| `race_progress` | `lap / total_laps` |
| `position_vs_grid` | Places gained relative to grid; positive means gained |
| `position_change` | Difference in position number from previous lap; positive means position number increased |
| `rolling_lap_time_ms` | Rolling mean lap time over up to the previous three rows |
| `pace_delta_to_fastest_ms` | Lap time minus fastest lap time on that race lap |

## Pit, tire, and strategy proxies

| Columns | Meaning |
|---|---|
| `pit_stop_this_lap` | Ergast-derived binary pit-stop indicator |
| `cumulative_pit_stops` | Cumulative pit-stop count |
| `laps_since_last_pit` | Tire-age proxy; pit lap carries pre-reset age, counter resets for next lap |
| `pit_duration_ms` | Ergast pit duration in milliseconds |
| `pit_stop_duration_s` | OpenF1 pit duration in seconds where available |
| `tire_age_ratio` | `laps_since_last_pit / total_laps` |
| `drs_zone_proxy` | Rule-based DRS proximity flag (gap threshold 1,250 ms; not activation ground truth) |
| `pit_window_proxy` | Basic 15–30 lap heuristic feature; distinct from the engine's ratio-based urgency rule |
| `compound` | OpenF1 tire compound where available |
| `stint_number` | OpenF1 stint index where available |
| `tyre_age_at_stint_start` | OpenF1 tire age at stint start where available |

## OpenF1 lap and weather enrichment

| Columns | Meaning |
|---|---|
| `date_start`, `date_openf1` | OpenF1 lap/weather timestamps |
| `duration_sector_1`, `duration_sector_2`, `duration_sector_3` | Sector durations |
| `i1_speed`, `i2_speed`, `st_speed` | Intermediate and start/finish speed trap values |
| `is_pit_out_lap` | OpenF1 indicator that lap follows a pit stop |
| `lap_duration` | OpenF1 lap duration |
| `segments_sector_1`, `segments_sector_2`, `segments_sector_3` | OpenF1 mini-sector segment data |
| `air_temperature`, `track_temperature` | Air and track temperature |
| `rainfall` | OpenF1 rainfall indicator |
| `humidity` | Relative humidity |
| `pressure` | Atmospheric pressure |
| `wind_speed`, `wind_direction` | Wind readings |
| `has_openf1_telemetry` | Indicator that OpenF1 enrichment is present on the row |

## Outcome and quality flag

| Columns | Meaning |
|---|---|
| `statusId` | Ergast finishing status identifier |
| `points` | Championship points awarded |
| `positionOrder` | Official final classification order |
| `won` | Binary target: driver won the race |
| `anomalous_lap_time` | Flag for anomalously long lap-time rows; not a race-outcome label |

The model excludes identifiers, text fields, the target, and outcome/leakage fields. See `src/features/train_model.py` for the current exclusion logic.
