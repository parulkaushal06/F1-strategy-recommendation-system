# Strategy engine

`src/strategy/recommend_action.py` defines `StrategyEngine`. It combines the calibrated model's win probability with separate rule-based recommendations. The output is for historical analysis and experimentation, not a trained policy or live pit-wall instruction.

## Win probability

The calibrated classifier estimates a probability for one driver/lap feature row. The API normalizes the field's raw calibrated scores to sum to 100% for current probabilities and lap histories. This produces relative field shares; the independent row model is not jointly trained across the field.

## Pit recommendation

Pit urgency uses `tire_age_ratio`, pace delta, and position trend. Default ratio thresholds are 0.076923, 0.433333, and 0.492958, derived from pre-pit q10/q90/q95 through 2020. Tire-age contributes up to a weighted 70 points, pace degradation up to 20, and a losing position trend 10. Scores >=70 return `PIT NOW`; scores >=40 return `CONSIDER PIT`; lower scores return `STAY OUT`. A row already marked `pit_stop_this_lap == 1` returns N/A. `tools/evaluate_pit_oos.py` evaluates next-lap pit alerts on 2021–2024; combined `PIT NOW` precision is 5.4% with an 8.7% false-positive rate, so this remains a weak heuristic.

The model's simulated pit-now probability is returned as context, not used as the sole pit decision rule. The pit simulation applies the median observed pit duration where available (fallback 22 seconds), updates simplified tire/pace/gap features, and reruns the model. This is a row perturbation, not a full race simulation.

## DRS, ERS, and race craft

- **DRS:** `drs_zone_proxy` is set using a 1,250 ms gap-to-ahead threshold. A leader is excluded because its stored zero gap is an artifact. This estimates proximity/eligibility; it does not confirm DRS activation.
- **ERS:** recommends proxy overtake mode when DRS proxy is available and pace delta exceeds 300 ms. Real ERS deployment data is unavailable.
- **Race craft:** computes gap behind from the same-lap field snapshot. It uses a 1,250 ms threshold for defending/attacking, requires pace delta below 300 ms for attack, and uses a two-threshold distance for comfortable pace management. Without the full field, gap-behind is unknown.

`recommend_batch()` makes current and simulated pit-now model calls in batches for the field. It is used by the strategy endpoint to avoid two model calls per driver.

## What-if actions

`simulate_what_if()` combines zero or more supported actions: `pit`, `push`, `attack`, `drs`, and `overtake`. The endpoint returns the action list, current and simulated probabilities, change in percentage points, notes, and a verdict that states the assumptions.

| Action | Implementation assumption |
|---|---|
| `pit` | Median pit-loss data (fallback 22 s) and simplified feature changes |
| `push` | Illustrative 150 ms/lap pace gain |
| `attack` | Illustrative 800 ms gap closure |
| `drs` | Enables the DRS proxy feature; rejected for the leader |
| `overtake` | Assumes a pass completes and adjusts position/gap fields; rejected for the leader |

Pit timing comparison evaluates pit now and pit in 3, 5, or 8 laps. It does not simulate rivals, safety cars, weather evolution, tire compound choice, or future traffic.

## API and tests

The web API invokes `recommend_full()` for the selected driver and `recommend_batch()` for field context. Regression tests in `tests/test_strategy_engine.py` cover pit-lap N/A behavior, fresh/old tire calls, leader false-attack behavior, and behind-gap handling.
