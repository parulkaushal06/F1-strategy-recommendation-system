# Data cleaning and validation

Cleaning is implemented in `src/data/clean_data.py`; it is not only a notebook procedure. Run it after `src/data/final_merge.py` to write `data/processed/cleaned_dataset.csv`.

## Checks and fixes represented in the pipeline

- Merge code checks required inputs and output fields, and reports actionable errors when important files or columns are missing.
- OpenF1 weather joins can suffix shared session identifiers. `consolidate_openf1.py` coalesces those IDs before the later driver join; `final_merge.py` also handles suffixed IDs defensively.
- OpenF1 stint boundaries can assign two compounds to a driver/lap. Consolidation keeps the later stint's value and removes duplicate `(session_key, driver_number, lap_number)` rows.
- Ergast pit flags are retained for historical coverage. OpenF1 pit records support enrichment and cross-source checks.
- The lap counter records tire age on a pit lap before resetting for the next lap. This preserves pre-stop age for strategy features.
- Very long lap times are flagged as `anomalous_lap_time`, rather than silently represented as ordinary laps. The API exposes this flag in strategy metadata.

## Current local snapshot

The cleaned file has 320,274 rows and 66 columns. Earlier documentation's 64/66/68-column counts referred to different intermediate or older snapshots; the actual cleaned CSV header is authoritative. Approximately 23,431 rows contain OpenF1 enrichment, with uneven coverage by field and season.

Historical checks recorded in project reports include full driver-code agreement on overlapping rows and 98.9% pit-stop agreement. Some remaining differences were associated with missing OpenF1 pit responses. When a source request failed, absence of a record is not a confirmed no-stop observation.

## Revalidate after changing inputs

Check duplicate `(raceId, driverId, lap)` keys, required columns, identifier and label nulls, pit counter behavior, and OpenF1 join coverage. Compare sources only where both sources provide observations. Historical validation values are not guarantees for newly collected data.
