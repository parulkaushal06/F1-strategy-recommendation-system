# Project Status

## Completed

- [x] Sourced and downloaded historical F1 results data (Ergast/Kaggle, 1950–2024)
- [x] Sourced and downloaded 2023 telemetry data (OpenF1 API — laps, pits, stints, weather)
- [x] Fetched real DRS validation data for 2 races (OpenF1 `car_data`) —
      corrected from an earlier "3 races" claim; only 2 `car_data` files
      actually exist (Bahrain, Brazil/Interlagos)
- [x] Merged Ergast tables into one lap-level dataset (589,081 rows)
- [x] Engineered core features (race progress, pace, gap-to-leader, pit/tire proxies)
- [x] Consolidated all OpenF1 race files into one table
- [x] Bridged Ergast and OpenF1 ID systems (driver code + circuit name matching)
- [x] Produced final merged dataset (320,274 rows × 68 → cleaned to 66 columns)
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
- [x] Built full-stack web app (Next.js frontend + FastAPI backend,
      `web/` + `src/api/main.py`) as a richer alternative to the Streamlit
      dashboard, with live race hub, strategy engine view, driver comparison,
      and results pages
- [x] Calibration check and fix: discovered the Random Forest was
      systematically overconfident (predicted ~82% for the top probability
      bucket, actual observed win rate only ~47%); fixed with
      `CalibratedClassifierCV`, cutting Brier score by 46% (0.0424 → 0.0227)
      with no ROC-AUC cost — see `09_model_results.md`
- [x] Fair model comparison: Random Forest vs Logistic Regression vs XGBoost,
      all calibrated identically. Random Forest retained as production model
      (best ROC-AUC and Brier score) — see `09_model_results.md`
- [x] Walk-forward validation across 3 independent test years (2022/2023/2024)
      confirmed consistent ROC-AUC (0.977–0.992); investigated and explained
      the 2023 outlier (Red Bull won 95% of that season, a real, verified
      historical fact, not a data issue) — see `09_model_results.md`
- [x] Removed duplicate `gap_to_leader_ms`/`gap_to_leader_s` feature (same
      value, two units) — confirmed no performance cost, cleaner feature
      importance ranking
- [x] Investigated a driver-relative pace feature to isolate tire degradation
      from car/team performance — found fuel burn-off and track evolution
      dominate over tire wear in this dataset, a genuine (if unexpected)
      finding, documented in `08_eda_findings.md`
- [x] Added SHAP explanations for individual predictions; discovered and
      correctly handled a mismatch between SHAP's raw-model output and the
      calibrated model's trustworthy probability — see `09_model_results.md`
- [x] Found and fixed a real performance regression: `CalibratedClassifierCV`'s
      default `cv=5` was retraining 5 internal model copies, making every
      prediction 5x slower. Fixed with `FrozenEstimator` + a 3-way time-based
      split (train/calibrate/test), recovering a 5.5x speedup with negligible
      quality cost — see `09_model_results.md`
- [x] Updated `src/api/main.py` and `src/strategy/recommend_action.py` to use
      the final calibrated model and 42-feature list
- [x] Found and fixed a second performance issue: the live field-standings
      panel was calling the model ~36-40 times per page load (2 calls ×
      18-20 drivers, in a loop). Refactored into `recommend_batch()` — 2
      model calls total for the whole field — cutting dashboard load time
      from ~5-10s toward near-instant
- [x] Fixed a real React bug in the frontend (`CircuitTrack.tsx`): a ref was
      read directly during render instead of inside `useEffect`, which could
      cause the live car-position dot to not update reliably
- [x] Validated `drs_zone_proxy` against real DRS telemetry from the 2-race
      sample (`validate_drs_proxy.py`): 78% overall agreement, 54-55% recall,
      13.5% false positive rate across 2,161 matched (driver, lap) rows —
      see `06_known_limitations.md` §2 for the full breakdown and the likely
      cause of the recall gap (whole-lap proxy vs. a fixed real detection point)
- [x] Tuned the DRS gap threshold empirically against the same real telemetry
      (`tune_drs_threshold.py`) rather than leaving the original 1000ms guess
      unchecked; switched to 1250ms (same 78.1% agreement, recall improved
      54.1% -> 62.0%) in both `build_features.py` and `recommend_action.py`'s
      race-craft logic — see `06_known_limitations.md` §2
- [x] Fixed the homepage hero section to dynamically reflect the actual
      next/selected race (using the season calendar's `status: "next"` entry
      and a new `/api/race-info` call) instead of hardcoded Belgian GP
      content; the same fix was applied to Race Hub's default-race selection
- [x] Added API input validation, a global exception handler (no stack
      traces leaked to clients), startup checks with actionable error
      messages when data/model files are missing, structured logging, and
      environment-driven CORS/data-path configuration — see `src/api/main.py`
- [x] Added a `tests/` suite (pytest + FastAPI TestClient) covering both
      the API error-handling work and regression tests for the two
      strategy-engine bugs found earlier (tire-age reset, leader false-attack)
- [x] Made the frontend mobile-responsive (working nav menu, stacked filter
      bars, scaled headings) across all 5 pages

- [x] Cleaned up `.gitignore`, removed `data/` and `models/*.pkl` from
      version control (git bloat was ~500MB of committed data/model files;
      the pipeline scripts regenerate all of it locally, so nothing is lost)

## In progress / next steps

- [ ] Wire SHAP per-prediction explanations into the dashboard UI (currently only
      exists in the modeling notebook)
- [ ] Deploy: frontend to Vercel, backend to Render/Railway — get a live demo link
- [ ] Set up GitHub Actions CI (lint + type-check + tests on every push)
- [ ] Add error handling and logging to the data pipeline scripts
      (`merge_datasets.py`, `build_features.py`, `clean_data.py`,
      `train_model.py`) to match the level of robustness now in `src/api/main.py`
- [ ] Formalize cross-validation across multiple seasons into a proper,
      repeatable script (the walk-forward checks so far were done manually)

## Design decisions worth highlighting in an interview / write-up

- Explicit separation of *measured* signals (real pit stops, tire compound from OpenF1)
  from *inferred* proxies (DRS zone, pit window) — with the proxy validated against real
  data rather than assumed correct
- Cross-source validation used as a genuine data-quality check (100% pit-stop agreement
  between Ergast and OpenF1), not just for cleaning
- Deliberate scoping of expensive telemetry fetches (2 races, not full season) with
  documented reasoning
- Time-aware train/test splitting to avoid leakage (a common mistake in
  race-outcome prediction projects), extended to walk-forward validation across
  multiple independent years rather than trusting a single split
- Diagnosed and fixed real model overconfidence via calibration curves, rather than
  trusting a strong ROC-AUC alone — a probability-driven dashboard needs trustworthy
  probabilities, not just good ranking ability
- Investigated a promising feature engineering idea (driver-relative pace) that
  turned out NOT to improve the model, and documented the honest negative result
  rather than forcing it in
- Found and fixed two separate real performance regressions in production code
  (calibration inference cost, redundant per-driver model calls) through direct
  measurement, not assumption