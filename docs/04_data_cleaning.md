# Data Cleaning

Performed in `notebooks/02_data_cleaning.ipynb`. The guiding principle throughout:
**check before you fix.** Every deletion or fill below was preceded by a diagnostic
check confirming it was safe — nothing was dropped or filled blind.

## 1. Core identifier check

Confirmed zero nulls in `raceId`, `driverId`, `lap`, `position`, `grid`, `year`, `won` —
if any of these were missing, it would indicate a bug upstream in the merge pipeline,
not a cleaning task. All clear.

## 2. Duplicate ID columns (merge suffix collisions)

**Issue found**: `session_key` and `meeting_key` each appeared 3 times
(`session_key_x`, `session_key_y`, `session_key`). Root cause: in
`consolidate_openf1.py`, the weather merge used `pd.merge_asof` only for sessions that
had weather data; rows that skipped that merge kept the plain column name, while rows
that went through it got pandas' automatic `_x`/`_y` suffixes for the naming collision.

**Validation before fixing**: confirmed the three columns were never simultaneously
populated for the same row (i.e., not conflicting values, just split across different
row subsets).

**Fix**: coalesced into a single column using `combine_first()`, dropped the duplicates.
Result: 1,357 non-null values in both `session_key` and `meeting_key` after the fix —
counts matched exactly, confirming no data was lost.

## 3. Duplicate pit-stop flag

**Issue found**: `pit_stop_this_lap` (derived from Ergast lap-time deltas in
`merge_datasets.py`) and `pit_stop_this_lap_openf1` (from OpenF1's real `/pit` endpoint)
— two independent measurements of the same event.

**Validation**: compared both columns across all 1,357 rows where both existed.
**Result: 100% agreement, zero mismatches.** This is a meaningful finding — it validates
that the Ergast-derived pit-stop feature is accurate, cross-checked against real
telemetry from an independent source.

**Fix**: dropped `pit_stop_this_lap_openf1`, kept the Ergast version since it covers all
years (OpenF1 only covers 2023).

## 4. Duplicate driver/team identity columns

**Issue found**: `full_name`, `name_acronym`, `team_name` (OpenF1) duplicated
`driverRef`, `code`, `constructor_name` (Ergast).

**Validation**:
- `code` vs `name_acronym`: **100% agreement** across all 1,357 overlapping rows —
  confirms the driver-code bridge built in `final_merge.py` was correct.
- `constructor_name` vs `team_name`: same teams, different naming conventions (e.g.
  Ergast's "Alpine" vs OpenF1's "Alpine F1 Team", "Red Bull" vs "Red Bull Racing") —
  not an error, just a labeling difference.

**Fix**: dropped all three OpenF1 duplicates, kept Ergast's versions for consistency
across all years.

## Columns dropped in total

`session_key_x`, `session_key_y`, `meeting_key_x`, `meeting_key_y`,
`pit_stop_this_lap_openf1`, `full_name`, `name_acronym`, `team_name`

**Result: 72 columns → 64 columns.**

## OpenF1 telemetry coverage

*(Note: this section was originally written before the weather-merge bug below was
found and fixed. Numbers reflect the corrected dataset.)*

Of 320,399 total rows, **23,556 (≈7.4%)** carry real OpenF1 telemetry (tire compound,
session identifiers), and **22,168 (≈6.9%)** additionally have weather data — the rest
are Ergast-only. This is expected given OpenF1 only covers one season (2023) out of the
dataset's full 2011–2024 range, and only races that successfully matched during the
ID-bridging step. A `has_openf1_telemetry` flag column was added so the model can use
this as a feature (e.g., learn to weight telemetry-backed rows differently) rather than
treating missing telemetry as an error.

## Second bug found: driver-name merge also broken by the same root cause

After the first fix above, re-validating the pit-stop and driver-code checks on the
larger dataset (23,556 rows instead of 1,357) revealed the first fix was incomplete.

**Symptom**: driver-code agreement (`code` vs `name_acronym`) dropped from 100% to
~6% (1,388 true / 23,556 total) when re-checked on the larger dataset. Investigation
confirmed all 22,168 "mismatches" were actually `name_acronym = NULL`, not genuinely
wrong values.

**Root cause**: inside `consolidate_openf1.py`, the driver-name merge (`session_key` +
`driver_number` → `full_name`/`name_acronym`/`team_name`) runs **after** the weather
merge — but the weather merge is what originally split `session_key` into
`session_key_x`/`session_key_y` (see the first bug above). This meant the driver-name
merge was silently failing for the majority of rows, long before the data ever reached
`final_merge.py`. The earlier fix (coalescing `session_key` inside `final_merge.py`)
only fixed race-ID matching — it ran too late in the pipeline to repair a join that had
already failed one script earlier.

A second issue was found at the same time: stint boundary laps (where one tire stint
ends and the next begins on the same lap number) were producing duplicate rows with two
different `compound` values for that lap — causing 250 duplicate rows in the merged
dataset.

**Fix**: added the same `session_key`/`meeting_key` coalesce step directly inside
`consolidate_openf1.py`, immediately after the weather merge and before the driver-name
merge — fixing the problem at its actual source rather than downstream. Also fixed
`expand_stints_to_laps()` to keep only the later stint's compound when two stints share
a boundary lap.

**Result after both fixes, re-validated on the full dataset**:

| Check | Result |
|---|---|
| Row-level duplicates (`raceId`, `driverId`, `lap`) | 0 (down from 250) |
| Driver code agreement (`code` vs `name_acronym`) | **100%** (23,431 / 23,431, zero real mismatches) — fully recovered |
| Pit-stop agreement (Ergast vs OpenF1) | **98.9%** (23,172 / 23,431) — see explanation below |
| `session_key` resolved | 23,511 / 23,511 laps (100%, up from 22,245) |
| Final merged dataset | 320,274 rows × 68 columns, 23,431 rows with real OpenF1 enrichment |

**On the remaining 1.1% pit-stop disagreement**: traced to 7 out of 22 races where
OpenF1's `/pit` endpoint failed to return data after retries during the original
collection step (`fetch_openf1.py`) — a known upstream gap, visible in that script's
console output at the time. For those races, `pit_stop_this_lap_openf1` defaults to 0
for every lap (no data, not a false observation), which disagrees with Ergast's correct
values on the small number of laps where a real pit stop happened. This is a documented
data-collection gap, not a pipeline bug — no further fix applied; these rows are simply
noted as lower-confidence for pit-stop cross-validation.

**Lesson learned (both bugs)**: a duplicate-column bug introduced by one merge step
(`merge_asof` creating `_x`/`_y` suffixes) can silently break *every subsequent* merge
in the same script that depends on that column — not just the step immediately after
it. When fixing this kind of bug, trace forward through the entire script to check every
later use of the affected column, not just the first one found.