# Exploratory analysis findings

This document summarizes findings recorded from the cleaned historical dataset and notebooks. Treat numeric correlations as descriptive, not causal. The current feature selection and training logic live in `src/features/train_model.py`.

## Outcome imbalance and leakage

Winning rows are uncommon (about 5.35% in the historical snapshot). Accuracy alone would therefore be misleading; evaluation uses ROC-AUC, precision, recall, and Brier score. `points`, `positionOrder`, and `statusId` are excluded from model inputs because they describe the race outcome or finishing state. The target is `won`.

## Signals in the data

Recorded EDA found strong relationships between win outcome and in-race position, grid position, and gaps. This matches the production model's saved feature-importance ranking: `position`, `gap_to_leader_s`, `gap_per_lap_covered_s`, `grid`, and `gap_to_ahead_ms` lead the 2024 model list. `drs_zone_proxy` is derived from gap and should not be interpreted as an independent causal factor.

Weather and speed-trap fields had weak standalone correlations in the available OpenF1 subset. Their coverage is limited, and low simple correlation does not prove they are useless in all interactions.

## Pace and tire interpretation

The EDA investigated driver-relative pace as a way to separate tire wear from car performance, fuel burn, and track evolution. Historical aggregate lap times can improve during a stint even while tires degrade, so raw lap-time trend is not a clean tire-degradation measurement. The strategy engine therefore labels its tire-age and pace logic as heuristic rather than treating it as a learned physical tire model.

## Use in model development

Feature inclusion is determined by code exclusions and training inputs, not solely by EDA correlation. See `src/features/train_model.py` and `docs/09_model_results.md` for the saved evaluation. Re-run notebook analysis after rebuilding the source data; the figures here describe the checked-in report snapshot.
