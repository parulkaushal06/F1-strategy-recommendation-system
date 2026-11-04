# Win-probability model results

This page reflects the saved artifacts `models/model_metrics.json`, `reports/cross_validation_results.csv`, and `reports/baseline_comparison.csv`. Re-run training and evaluation after changing source data or features.

## Production training setup

`src/features/train_model.py` trains a `RandomForestClassifier` with 200 trees, maximum depth 12, minimum leaf size 5, balanced class weights, and fixed random seed 42. Missing numeric feature values are filled with `-999`. Feature selection excludes text fields, identifiers, the `won` target, leakage fields, and duplicate-unit `gap_to_leader_ms`.

The current temporal split is explicit: years before 2023 train the forest, 2023 fits isotonic calibration through `CalibratedClassifierCV(FrozenEstimator(...))`, and 2024 is held out for test metrics. Saved split sizes are 269,314 train, 24,386 calibration, and 26,574 test rows.

## Held-out 2024 metrics

| Metric | Saved value |
|---|---:|
| ROC-AUC | 0.9746 |
| Brier score | 0.0237 |
| Precision | 0.7640 |
| Recall | 0.6884 |

Precision and recall use the estimator's default classification threshold; the dashboard displays probability scores rather than a binary winner decision.

## Walk-forward evaluation

`src/features/cross_validate.py` trains each fold only on prior seasons, calibrates on the immediately preceding season, and tests on the selected year. Saved folds cover 2018–2024. Mean ROC-AUC is 0.9708 (standard deviation 0.0113); mean Brier score is 0.0257. Individual fold data is in `reports/cross_validation_results.csv`.

## Baselines and interpretation

The saved 2024 comparison reports ROC-AUC 0.9696 for current-position-only, 0.9747 for position plus race progress logistic regression, and 0.9746 for the calibrated Random Forest. The model's aggregate edge over simple race-state baselines is small. Position and gaps carry much of the signal; a high AUC should not be described as proof that the strategy recommendations improve outcomes.

## Feature importance and calibration

The saved top features are position, gap to leader in seconds, gap per lap, grid, and gap to ahead. The API exposes top raw Random Forest importances. Calibration uses only the 2023 season; saved 2024 bucket analysis shows underconfidence in some middle buckets and overconfidence in upper buckets. A multi-season calibration analysis would be needed before claiming reliable calibration across eras.

SHAP explanations are available from `src/features/explain.py` and `GET /api/explain`. SHAP describes raw-model contributions, while the displayed headline probability is calibrated; those values are not a decomposition of the calibrated score.
