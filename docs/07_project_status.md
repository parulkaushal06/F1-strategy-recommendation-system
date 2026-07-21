# Project Status

## Completed

- [x] Sourced and downloaded historical F1 results data (Ergast/Kaggle, 1950–2024)
- [x] Sourced and downloaded 2023 telemetry data (OpenF1 API — laps, pits, stints, weather)
- [x] Fetched real DRS validation data for 3 races (OpenF1 `car_data`)
- [x] Merged Ergast tables into one lap-level dataset (589,081 rows)
- [x] Engineered core features (race progress, pace, gap-to-leader, pit/tire proxies)
- [x] Consolidated all OpenF1 race files into one table
- [x] Bridged Ergast and OpenF1 ID systems (driver code + circuit name matching)
- [x] Produced final merged dataset (320,274 rows × 72 → cleaned to 64 columns)
- [x] Cleaned data with validated fixes (duplicate columns resolved, cross-source
      agreement checks passed — see `04_data_cleaning.md`)
- [x] Built full data dictionary
- [x] Row-level duplicate check (zero found — confirms merge key integrity)
- [x] Data type enforcement (Int64 for identifier columns)
- [x] Lap-time outlier investigation and flagging (562 red-flag/safety-car artifacts
      identified and flagged, not dropped — see `04_data_cleaning.md` section 5)
- [x] Found and fixed two upstream merge-pipeline bugs (weather and driver-name data
      silently failing to join due to a `session_key` column-splitting side effect —
      see `04_data_cleaning.md` for full root-cause writeup)
- [x] Re-validated cross-source checks on the corrected, larger dataset (driver code:
      100% agreement; pit stops: 98.9% agreement, remaining gap explained by a known
      upstream OpenF1 data-collection gap, not a pipeline bug)
- [x] Rebuilt `02_data_cleaning.ipynb` as a clean final version (removed debugging/
      investigation cells now that root causes are documented separately)
- [x] Saved final cleaned dataset (`data/processed/cleaned_dataset.csv`,
      320,274 rows × 66 columns)
- [x] Trained baseline win-probability model (`RandomForestClassifier`,
      time-based train/test split by season to avoid leakage) — ROC-AUC 0.976,
      calibrated (91.4% avg predicted probability for actual winners, 6.5% for
      non-winners) — see `09_model_results.md`
- [x] Feature importance analysis (position and gap-to-leader dominate — see
      `09_model_results.md`, surfaced in the dashboard too)
- [x] Found and fixed a second upstream pipeline bug: `laps_since_last_pit`
      was resetting to 0 on the same lap a pit stop happened (instead of the
      lap after), meaning 100% of real pit-stop rows recorded 0 tire age.
      Fixed in `merge_datasets.py`; full pipeline rerun and model retrained
      on corrected data — see `10_strategy_engine.md` §3.1
- [x] Built strategy recommendation logic (`src/strategy/recommend_action.py`):
      pit timing (73% recall / 0.7% false-positive rate, validated on 300
      samples each), DRS, ERS (proxy), and race-craft (attack/defend/manage
      pace) — see `10_strategy_engine.md`
- [x] Built dashboard (Streamlit, `dashboard/app.py`) showing live win
      probability + full recommendation checklist, lap by lap — see
      `11_dashboard.md`

## In progress / next steps

- [ ] Resume exploratory data analysis (EDA) — class balance and distributions already
      done in `03_eda.ipynb`; re-run correlation ranking on the corrected, larger
      OpenF1-enriched dataset (previous run was on the broken 1,357-row subset)
- [ ] Validate `drs_zone_proxy` against real DRS data from the 3-race telemetry sample
- [ ] Model evaluation and validation on more seasons / cross-validation, beyond the
      single held-out test year currently used

## Design decisions worth highlighting in an interview / write-up

- Explicit separation of *measured* signals (real pit stops, tire compound from OpenF1)
  from *inferred* proxies (DRS zone, pit window) — with the proxy validated against real
  data rather than assumed correct
- Cross-source validation used as a genuine data-quality check (100% pit-stop agreement
  between Ergast and OpenF1), not just for cleaning
- Deliberate scoping of expensive telemetry fetches (3 races, not full season) with
  documented reasoning
- Time-aware train/test splitting planned to avoid leakage (a common mistake in
  race-outcome prediction projects)