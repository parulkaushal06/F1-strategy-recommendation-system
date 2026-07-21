# Data Merging Pipeline

Four scripts, run in order, take the raw downloaded files and produce one unified,
model-ready dataset.

```
merge_datasets.py    → data/interim/lap_level_merged.csv     (589,081 rows)
build_features.py    → data/processed/lap_level_features.csv
consolidate_openf1.py → data/interim/openf1_lap_level.csv
final_merge.py        → data/processed/final_merged_dataset.csv   (320,274 rows × 72 cols)
```

## Step 1: `merge_datasets.py` — build the Ergast lap-level table

Joins `lap_times.csv` (the row-level granularity: one row per driver per lap) with:
- `races.csv` → year, round, circuit, date
- `results.csv` → grid position, final position, points, status
- `drivers.csv`, `constructors.csv`, `circuits.csv` → readable names

Also computes, per lap:
- **Gap to leader**: cumulative race time compared to whoever's leading that lap
- **Pit stop features**: whether a pit happened this lap, cumulative pit count,
  laps since last pit (tire-age proxy)
- **Label**: `won = 1` if `positionOrder == 1` for that race

Output: 589,081 rows (one per driver per lap, all years with lap-time data).

## Step 2: `build_features.py` — feature engineering

Takes the merged table and:
1. Filters to `year >= 2011` (see `01_data_sources.md` for why)
2. Adds race-progress-normalized features (`race_progress`, `gap_per_lap_covered_s`) so
   a gap means the same thing whether it's lap 5 or lap 55
3. Adds pace features (`rolling_lap_time_ms`, `pace_delta_to_fastest_ms`)
4. Adds rule-based strategy proxy flags (`drs_zone_proxy`, `pit_window_proxy`) — used
   before real OpenF1 telemetry is available for a given row

## Step 3: `consolidate_openf1.py` — stack and join OpenF1's own tables

OpenF1 data was downloaded as separate files per race (laps, pits, stints, weather).
This script:
1. Concatenates all races' files into 4 unified tables
2. Expands `stints.csv` (stored as lap ranges, e.g. "lap 5–20 = medium tire") into one
   row per lap, so it lines up with the laps table
3. Joins pit stops and tire data directly (exact key match on session/driver/lap)
4. Joins weather using nearest-timestamp matching (`pd.merge_asof`), since weather
   readings and lap timestamps don't align exactly
5. Joins driver name/team info

## Step 4: `final_merge.py` — bridging two different ID systems

This is the trickiest part: Ergast and OpenF1 identify races and drivers differently.

| | Ergast | OpenF1 |
|---|---|---|
| Race identifier | `raceId` (integer) | `session_key` (integer) |
| Driver identifier | `driverId` (integer) | `driver_number` (integer) |

Neither ID system overlaps, so a **bridge table** was built for each:

**Driver bridge**: matched on the 3-letter driver code, which both sources happen to
share (Ergast's `code` field, e.g. "VER", vs OpenF1's `name_acronym`, e.g. "VER"). This
matched cleanly — 22 unique drivers for the 2023 season (20 regular + mid-season
substitutes), all correctly mapped.

**Race bridge**: matched on circuit name — but the two sources use different naming
conventions (Ergast's `circuitRef`, e.g. `"bahrain"`, vs OpenF1's `circuit_short_name`,
e.g. `"Sakhir"`). Automatic matching only succeeded for races where the names happened
to align; the rest required a manual lookup table, e.g.:

| OpenF1 name | Ergast `circuitRef` |
|---|---|
| Sakhir | bahrain |
| Melbourne | albert_park |
| Monte Carlo | monaco |
| Spa-Francorchamps | spa |
| Yas Marina Circuit | yas_marina |

One circuit (**Imola**) never matched — correctly, since the 2023 Emilia Romagna Grand
Prix was cancelled due to flooding and doesn't exist in the 2023 Ergast results.

Once both bridges exist, OpenF1 data is merged onto the Ergast lap-level table on
`(raceId, driverId, lap)`.

## Result

Final dataset: **320,274 rows × 72 columns** (later cleaned to 64 — see
`04_data_cleaning.md`). Only rows from 2023 races that successfully matched carry real
OpenF1 telemetry; all other rows (2011–2022, plus any 2023 rows that didn't match) have
those columns as `NaN`, which is expected and by design, not a data quality failure.