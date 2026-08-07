# Model Results — Baseline Win Probability Model

## Setup

- **Model**: `RandomForestClassifier` (n_estimators=200, max_depth=12, min_samples_leaf=5,
  class_weight='balanced')
- **Features**: 43 numeric features, explicitly excluding leakage columns (`points`,
  `positionOrder`, `statusId`) and identifiers — see `04_modeling.ipynb` section 2
- **Train/test split**: time-based by race year, not random — train on 2011–2023
  (293,700 rows, 5.34% won), test on 2024 only (26,574 rows, 5.43% won). This ensures no
  race appears in both sets and mirrors real deployment (train on past, predict on new
  races).
- **Missing values**: filled with -999 sentinel (not mean/median), so the model can
  distinguish "no data" from a real low value — relevant since ~93% of rows lack real
  OpenF1 telemetry (weather, speed trap columns).

## Results

| Metric | Score |
|---|---|
| ROC-AUC | **0.977** |
| Precision | 0.491 |
| Recall | 0.857 |
| F1 score | 0.624 |

**ROC-AUC of 0.977** indicates strong discriminative power — given one winning-driver
row and one non-winning row at random, the model correctly ranks them 97.7% of the time.

**Precision/recall trade-off** is a deliberate result of `class_weight='balanced'`,
which counters the 5.35% win rate found during EDA (see `08_eda_findings.md`). This
prioritizes catching true winners (86% recall) at the cost of more false positives
(49% precision) at the default 0.5 threshold. For the dashboard's actual use case —
displaying a continuous win probability rather than a binary yes/no — this is an
acceptable trade-off, since the raw probability score matters more than the threshold.

## Feature importance (Objective 1 answer)

Top features, Random Forest importance:

| Rank | Feature | Importance |
|---|---|---|
| 1 | `position` | 0.224 |
| 2 | `gap_to_leader_ms` | 0.156 |
| 3 | `gap_to_leader_s` | 0.150 |
| 4 | `gap_to_ahead_ms` | ~0.05 |
| 5 | `gap_per_lap_covered_s` | ~0.04 |
| 6 | `grid` | ~0.04 |
| 7 | `drs_zone_proxy` | ~0.03 |
| 8 | `pace_delta_to_fastest_ms` | ~0.02 |

**Comparison to the linear correlation ranking from EDA**: broadly consistent —
position and gap-based features dominate in both. `drs_zone_proxy` ranks lower here
(7th) than in the linear correlation check (2nd), suggesting its relationship with
winning is partly captured indirectly through the gap-based features it's derived from
(it's built from `gap_to_ahead_ms`), rather than being a fully independent signal —
worth noting rather than treating as a contradiction.

**Known redundancy**: `gap_to_leader_ms` and `gap_to_leader_s` are the same value in
different units, so their combined importance (~0.31) is likely split across two nearly
duplicate columns rather than genuinely representing two distinct signals. A future
iteration should drop one.

## Known limitation: heavy missingness in weather/telemetry features

~93% of rows lack real OpenF1 telemetry (weather, speed trap columns), filled with a
-999 sentinel. This risks the model learning "-999 means no telemetry" as a pattern
distinct from the `has_openf1_telemetry` flag already provided for this purpose,
potentially diluting these features' real signal. Planned follow-up: compare model
performance with these columns included vs excluded, to check whether they're adding
genuine value or just noise from the missingness pattern.

## Calibration

Initial calibration check revealed the Random Forest was systematically overconfident:
predicted ~81.6% win probability in the top bucket, but actual observed win rate was
only ~46.9% — a real, meaningful miscalibration, not noise (visible across the whole
calibration curve, not just one bucket).

**Fix**: `CalibratedClassifierCV` (isotonic method) applied on top of the trained model.

| | Before | After |
|---|---|---|
| Brier Score | 0.0424 | **0.0227** (-46%) |
| ROC-AUC | 0.9762 | 0.9770 (unchanged) |

Calibration meaningfully improved probability trustworthiness without costing any
ranking performance — a clean win, not a trade-off.

## Model comparison (fair, all models calibrated identically)

| Model | ROC-AUC | Precision | Recall | Brier Score |
|---|---|---|---|---|
| **Random Forest (calibrated)** | **0.977** | 0.76 | 0.68 | **0.023** |
| Logistic Regression (calibrated) | 0.966 | 0.68 | **0.72** | 0.026 |
| XGBoost (calibrated) | 0.963 | **0.76** (tied) | 0.62 | 0.024 |

**Conclusion**: Random Forest retained as the production model. It wins on ROC-AUC and
Brier score — the two metrics most relevant to a probability-driven dashboard — even
under a fully fair comparison where every model received the same calibration
treatment (an earlier, uncalibrated-only comparison had made XGBoost look worse than
it really is, purely from the calibration gap, not genuine model quality).

## Walk-forward validation

Trained/tested across 3 independent year-cutoffs (train on all years before X, test on
year X) to confirm the strong single-year result wasn't a lucky split.

| Test Year | Train Rows | Test Rows | ROC-AUC | Precision | Recall | Brier Score |
|---|---|---|---|---|---|---|
| 2022 | 245,785 | 23,529 | 0.977 | 0.73 | 0.63 | 0.024 |
| 2023 | 269,314 | 24,386 | **0.992** | **0.88** | **0.83** | **0.014** |
| 2024 | 293,700 | 26,574 | 0.977 | 0.76 | 0.68 | 0.023 |

**ROC-AUC stayed consistently strong (0.977–0.992) across all three independent test
years** — genuine evidence of generalization, not a single-split fluke.

**2023 stood out as meaningfully easier to predict across every metric.**
Investigated rather than dismissed: 2023 was Red Bull's historically dominant season —
constructor win concentration for that year showed **Red Bull responsible for 95% of
all winning rows (1,263 of 1,325)**, matching real-world F1 history (Red
Bull/Verstappen won all but one race in 2023). When one team dominates this heavily,
grid position and gap-to-leader become cleaner, more decisive signals, making that
season genuinely easier to predict — a real, explainable pattern in the underlying
sport, not a data quality issue or lucky split.

**Overall conclusion**: the model generalizes reliably across seasons, with
performance varying in a way that has a clear, verified real-world explanation rather
than appearing arbitrary.

## Duplicate feature cleanup

Removed `gap_to_leader_ms` (kept `gap_to_leader_s` — same value, different units).
Confirmed via retraining: performance unchanged (ROC-AUC 0.9770→0.9774, Brier
0.0227→0.0226), while feature importance became more honest (previously split ~0.31
combined importance across two duplicate columns, now correctly concentrated in one:
`gap_to_leader_s` at 0.16).

## SHAP values for individual prediction explanations

**Motivation**: global feature importance shows what matters on average — not why a
SPECIFIC driver has a specific probability. Added SHAP (`TreeExplainer`) to explain
individual predictions for the dashboard.

**Validation**: top features by mean |SHAP value| closely matched the Random Forest's
built-in `feature_importances_` ranking (position, gap_to_leader_s, grid, gap_per_lap_
covered_s, gap_to_ahead_ms — same top 5, nearly identical order) — two independent
methods agreeing strengthens confidence in the Objective 1 conclusion.

**Important finding — SHAP explains the raw model, not the calibrated output**:
verified that SHAP's base rate + sum of SHAP values reconstructs the model's RAW,
uncalibrated probability (e.g. 7.41% for a test row) — not the calibrated, trustworthy
probability actually shown on the dashboard (0.66% for that same row). This makes
sense: `class_weight='balanced'` affects the raw tree structure SHAP reads directly,
while calibration is a separate correction layer applied afterward.

**Design decision**: the dashboard's headline probability always comes from the
calibrated model. SHAP values are used only for directional reasoning ("this factor
pushed probability up/down") in the explanation text, never presented as if they sum
to the exact calibrated number — this distinction is stated explicitly rather than
glossed over, since presenting SHAP values as if they explained the calibrated number
would be technically inaccurate.

## Performance issue found and fixed: calibration made predictions 5x slower

**Symptom**: after deploying the calibrated model to the live dashboard, pages took
~10 seconds to load (previously near-instant with the uncalibrated model).

**Root cause**: `CalibratedClassifierCV(model, cv=5)` (the default calibration
approach used initially) doesn't just calibrate the existing model — it internally
**retrains 5 separate copies** of it (one per cross-validation fold) and averages
their predictions at inference time. This turned every prediction into ~5x the
computation (effectively ~1,000 trees instead of 200), which is barely noticeable for
a single one-off prediction in a notebook, but compounds badly when the dashboard
makes 30+ predictions per page load (the full lap-by-lap win probability trend).

**Fix**: switched to a three-way time-based split (train / calibrate / test on
separate years) combined with `CalibratedClassifierCV(FrozenEstimator(model))` —
calibrates the model **once** against a held-out calibration year, instead of
retraining internally. (Note: `cv='prefit'`, the older syntax for this same idea, is
deprecated in current scikit-learn in favor of `FrozenEstimator`.)

**Result**:

| | 5-fold calibration | FrozenEstimator calibration |
|---|---|---|
| Avg prediction time | 291 ms | **53 ms** (5.5x faster) |
| ROC-AUC | 0.977 | 0.975 |
| Brier Score | 0.023 | 0.024 |

Negligible quality difference, major speed improvement — a clear win once diagnosed
correctly rather than just tolerated as "the app is a bit slow now."

## Next steps

- [x] Compare against an XGBoost baseline
- [x] Walk-forward validation across multiple years
- [x] Calibration check and fix
- [x] Consolidate the duplicate gap-unit columns
- [x] Driver-relative pace feature investigation (see `08_eda_findings.md`)
- [x] SHAP values for individual prediction explanations
- [ ] Update dashboard/API (`src/api/main.py`, `src/strategy/recommend_action.py`) to
      load `win_probability_model_calibrated.pkl` and the updated 42-feature list
      instead of the original uncalibrated model
- [ ] Wire SHAP explanations into the dashboard's per-driver detail view
