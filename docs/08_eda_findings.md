# EDA Findings

Summary of exploratory analysis on `data/processed/cleaned_dataset.csv`
(320,274 rows, 66 columns). Full analysis in `notebooks/03_eda.ipynb`.

## Class balance

Winning is rare at the row level: **5.35%** of rows have `won = 1`. This matches
expectations (~1 winner per ~20-car field). **Implication**: accuracy alone is a
misleading metric for the win-probability model — a model predicting "never wins"
would score 94.65% accuracy while being useless. Precision, recall, and ROC-AUC will
be used instead.

## Data leakage identified — critical for modeling

`points` (correlation 0.64) and `positionOrder` (correlation -0.38) are **not valid
predictive features** — they describe the outcome itself (a driver earns points
*because* they won; `positionOrder == 1` *is* the win). Including these as model
inputs would be data leakage. **Action**: `points`, `positionOrder`, and `statusId`
are excluded from the model's feature set, kept only for reference/labeling.

## Strongest legitimate predictors of winning

| Feature | Correlation | Why it makes sense |
|---|---|---|
| `position` | -0.357 | Running further back makes winning less likely — expected, and known in real-time |
| `grid` | -0.323 | Starting further back makes winning less likely — known before the race starts |
| `gap_to_leader_s` | -0.190 | Bigger gap to the leader, less likely to win — expected |
| `drs_zone_proxy` | 0.304 | Being within 1s of the car ahead (DRS-eligible) has a meaningfully positive relationship with winning — the strongest engineered feature by far |

## Weather and raw speed: checked and ruled out as direct predictors

With real OpenF1 telemetry now correctly merged (23,431 enriched rows, up from a
broken ~1,357), weather columns (`air_temperature`, `rainfall`, `track_temperature`,
etc.) and speed-trap readings (`i1_speed`, `i2_speed`, `st_speed`) all show
near-zero correlation with `won` (all under 0.01 in magnitude).

**This is a legitimate finding, not a data quality issue**: weather affects every car
in a race roughly equally, so it wouldn't be expected to predict *who specifically*
wins — it more likely affects lap-time variance and strategy timing (e.g. when to pit)
rather than the win outcome directly. Similarly, raw top speed doesn't capture cornering
or race-craft, so it not correlating with winning on its own is expected, not surprising.

**Implication for the model**: these features are not dropped — they may still combine
usefully with other features in a non-linear model (e.g. Random Forest can capture
interactions a simple correlation can't) — but they're not expected to be top-ranked
individually in feature importance later.

## Weak individual signal, likely interaction effects

`race_progress`, `laps_since_last_pit`, `tire_age_ratio`, `pace_delta_to_fastest_ms`,
`cumulative_pit_stops` all show weak standalone correlation (under 0.03 in magnitude).
This doesn't mean they're unimportant — a linear correlation can't detect effects that
only appear in combination with other features (e.g. tire age might matter a lot, but
only conditional on race progress or weather). Feature importance from a tree-based
model (planned next) is expected to reveal more here than this linear check can.

## Pit stop strategy (see `03_eda.ipynb` section 6)

Most races are decided with a 1-stop strategy — 0 and 2 stops are both less common and
associated with worse average finishing position, matching real-world F1 strategy
knowledge.

## Next step

These findings directly inform feature selection for the win-probability model:
excluding leakage columns (`points`, `positionOrder`, `statusId`), prioritizing
position/gap/grid-based features, keeping the `drs_zone_proxy` as a headline
engineered feature, and retaining weaker features for the model to potentially combine
non-linearly rather than dropping them based on linear correlation alone.