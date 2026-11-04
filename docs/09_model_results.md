# Win-probability model results

This page reflects the saved artifacts `models/model_metrics.json`, `reports/cross_validation_results.csv`, and `reports/baseline_comparison.csv`. Re-run training and evaluation after changing source data or features.

## Production training setup

`src/features/train_model.py` trains a `RandomForestClassifier` with 200 trees, maximum depth 12, minimum leaf size 5, balanced class weights, and fixed random seed 42. Missing numeric feature values are filled with `-999`. Feature selection excludes text fields, identifiers, the `won` target, leakage fields, and duplicate-unit `gap_to_leader_ms`.

The current temporal split is explicit: years before 2021 train the forest, 2021–2023 fit isotonic calibration through `CalibratedClassifierCV(FrozenEstimator(...))`, and 2024 is held out for test metrics. Saved split sizes are 222,097 train, 71,603 calibration, and 26,574 test rows. The metrics JSON records scikit-learn and pandas versions.

## Held-out 2024 metrics

| Metric | Saved value |
|---|---:|
| ROC-AUC | 0.9754 |
| Brier score | 0.0222 |
| Precision | 0.7636 |
| Recall | 0.6891 |

Precision and recall use the estimator's default classification threshold; the dashboard displays probability scores rather than a binary winner decision.

## Walk-forward evaluation

`src/features/cross_validate.py` trains each fold only on prior seasons, calibrates on the previous three seasons, and tests on the selected year. Saved folds cover 2018–2024. Mean ROC-AUC is 0.9730 (standard deviation 0.0082); mean Brier score is 0.0250. For each fold, races are sampled as clusters for bootstrap confidence intervals; the 2024 fold has 24 races and 95.8% final-lap winner top-1 accuracy (95% CI 83.3–100%). Individual fold data and intervals are in `reports/cross_validation_results.csv`.

## Baselines and interpretation

The saved 2024 comparison reports ROC-AUC 0.9696 for current-position-only, 0.9747 for position plus race progress logistic regression, and 0.9754 for the calibrated Random Forest. The model's aggregate edge over simple race-state baselines is small. Position and gaps carry much of the signal; a high AUC should not be described as proof that the strategy recommendations improve outcomes.

## Feature importance and calibration

The saved top features are position, gap to leader in seconds, grid, gap per lap, and gap to ahead. The API exposes top raw Random Forest importances. Calibration uses 2021–2023; saved 2024 bucket analysis is closer overall but still shows mismatch in the 25–50% and 75–90% buckets, each with relatively few rows.

SHAP explanations are available on demand in the Strategy dashboard and from `GET /api/explain`. SHAP describes raw-model contributions, while the displayed headline probability is calibrated and field-normalized; those values are not a decomposition of the displayed score.

## Missing-feature ablation

`tools/feature_ablation.py` compares production `-999` sentinel handling, dropping features with missing values in the training years, and training-median imputation with missing indicators. On the 2024 holdout, ROC-AUC values were 0.9754, 0.9744, and 0.9757 respectively; Brier scores were 0.0222, 0.0227, and 0.0225. The small differences do not establish a general advantage beyond this test split. Results are in `reports/feature_ablation.csv`.
