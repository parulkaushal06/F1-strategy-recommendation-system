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

## Next steps

- [ ] Compare against an XGBoost baseline
- [ ] Consolidate the duplicate gap-unit columns
- [ ] Test model with/without heavily-missing weather/telemetry features
- [ ] Build the strategy recommendation logic (pit timing, DRS opportunity) using this
      model's probability output
- [ ] Integrate into the dashboard