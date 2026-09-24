# Strategy Recommendation Engine

`src/strategy/recommend_action.py` — turns a single race-state row (one driver,
one lap) into a full strategy recommendation: win probability, pit timing, DRS,
ERS, and race craft (attack/defend/manage pace).

## 1. Why this exists

Predicting *who wins* is the less interesting half of this project. The more
useful question, asked live during a race, is: **given the current situation,
what should this driver do right now to maximize their win probability?**
That's what this module answers.

## 2. Win probability (context signal)

Every recommendation is accompanied by the model's live win probability for
that driver at that lap (`current_win_probability`). This comes directly from
`models/win_probability_model.pkl` (see `09_model_results.md`). It's well
calibrated: rows that actually won the race average **91.4%** predicted
probability; rows that didn't win average **6.5%**. Spot-checked against a
real 2024 race, the eventual winner's probability climbs from ~95% to ~99.5%
over the race while leading, while a P4-P6 finisher correctly decays toward
near-zero.

## 3. Pit stop recommendation

### 3.1 The bug that was found and fixed

The original pit-window logic checked `laps_since_last_pit` against a fixed
15–30 lap range. It always said "STAY OUT" when tested against real pit-stop
laps. Root cause, found by checking the feature at scale:

- `laps_since_last_pit` (computed in `merge_datasets.py`) reset to `0` on the
  **same row** a pit stop happened, instead of the row after.
- Verified: **100% of the 11,371 real pit stops** in the dataset had
  `laps_since_last_pit == 0` recorded — the tire-age signal had already been
  wiped by the very event it was supposed to help predict.

Fixed in `merge_datasets.py`: the counter now records tire age *before* the
pit, then resets for the next lap. The whole pipeline (`merge_datasets.py` →
`build_features.py` → `consolidate_openf1.py` → `final_merge.py` →
`clean_data.py` → `train_model.py`) was rerun after the fix, and the model was
retrained on the corrected data (ROC-AUC 0.976, effectively unchanged from
0.977 pre-fix — expected, since position/gap features dominate the model
either way; the fix corrects tire-age data quality, not raw model accuracy).

### 3.2 Ratio-based window, not a fixed lap count

A fixed "15–30 laps" window doesn't scale with race length (53-lap vs 78-lap
races shouldn't share a window). Reconstructing the *real* tire age right
before actual pit stops (using the corrected data) gives:

| Percentile | Tire age ratio (laps_since_last_pit / total_laps) |
|---|---|
| 10th | 0.07 |
| 25th | 0.17 |
| 50th (median) | 0.26 |
| 75th | 0.36 |
| 90th | 0.46 |

`recommend_action.py` uses these to derive `PIT_WINDOW_RATIO_LOW = 0.12`,
`PIT_WINDOW_RATIO_HIGH = 0.45`, `PIT_WINDOW_RATIO_CRITICAL = 0.55`.

### 3.3 Continuous urgency score, not a binary flag

Instead of a single if/elif, `_pit_urgency_score()` returns a continuous 0–100
score blending:
- Tire age ratio (primary signal, ramps through the pit window) — weight 0.7
- Pace degradation vs. the fastest lap this round — up to 20 points
- Recent position trend (losing places) — 10 points

Thresholds: `>=70` → PIT NOW, `>=40` → CONSIDER PIT, else STAY OUT.

### 3.4 Validated results (300 samples each, not a handful of examples)

- **Recall: 73%** — of laps immediately before a real pit stop, correctly
  flags PIT 73% of the time. The 27% misses are mostly early/reactive stops
  (safety car, tire failure, undercut) that tire age alone can't predict from
  historical data.
- **False positive rate: 0.7%** — with tires genuinely fresh (≤5 laps old),
  almost never wrongly recommends pitting.

### 3.5 Known edge case, handled explicitly

If the input row already has `pit_stop_this_lap == 1`, that row shows
post-pit state (tire age ~0), not a "should I pit" decision point. The engine
returns `"N/A (this row already shows a pit stop happening this lap)"` instead
of silently giving a misleading answer.

## 4. DRS recommendation

Uses the existing `drs_zone_proxy` feature (`gap_to_ahead_ms <= 1000`, i.e.
within 1 second of the car ahead). Validated against real DRS telemetry from
a 2-race sample (Bahrain, Brazil/Interlagos): 78% overall agreement, 54-55%
recall, 13.5% false positive rate — see `06_known_limitations.md` §2 for the
full breakdown and `validate_drs_proxy.py` for the validation script itself.

## 5. ERS recommendation (proxy)

No public data source exposes real ERS deployment mode (see
`06_known_limitations.md` §1). "Use ERS Overtake Mode" is only recommended
when **both** a real overtaking opportunity exists (within DRS range) **and**
the driver is meaningfully off the pace (`pace_delta_to_fastest_ms > 300`),
since ERS's main strategic use is closing/completing a pass, not general
cruising. This is a proxy, and is labeled as such in every output.

## 6. Race-craft recommendation (attack / defend / manage pace)

Added because pit/DRS/ERS alone don't cover real strategy — attacking,
defending, and pace management matter too, and the dataset already has the
signals to support this: `gap_to_ahead_ms`, `pace_delta_to_fastest_ms`,
`position_change`.

### 6.1 A new derived signal: gap to the car behind

The dataset only ever computed `gap_to_ahead_ms` (looking forward). Knowing
whether to defend requires knowing how close the car **behind** is, which
can't be computed from a single driver's row in isolation — it needs the full
field's state for that lap. `StrategyEngine.compute_gap_to_behind_ms()` takes
a same-lap, all-drivers snapshot (in live use: the current lap's timing
sheet) and derives it on the fly. No pipeline rerun or model retraining
needed for this — it's computed at request time in `recommend_full()`.

### 6.2 Logic

- **DEFEND POSITION** (or **URGENTLY**, if also losing places): car behind
  is within DRS range (≤1000ms) and the driver doesn't have their own
  attacking chance ahead.
- **ATTACK**: car ahead is within DRS range and pace delta is competitive
  (<300ms off the fastest lap).
- **MANAGE PACE**: no car within 2x the DRS threshold either ahead or behind
  — safe to protect tires/engine rather than push.
- **HOLD STATION**: none of the above triggers.

### 6.3 Edge case found and fixed: the race leader

`gap_to_ahead_ms` is stored as `0.0` for every leader row (an artifact of
"nothing to diff against," not a real zero-gap reading). Before the fix, this
made `attacking_chance` true for the leader whenever their pace was also good
— which, being the leader, it usually is — producing a nonsensical "ATTACK"
call for the driver already in P1. Fixed by treating `position == 1` as
"nobody ahead" (`gap_ahead = None`) in `recommend_full()`.

### 6.4 Validated distribution (60 random lap-snapshots, ~1,150 driver-rows)

| Recommendation | Share |
|---|---|
| HOLD STATION | 39.1% |
| MANAGE PACE | 38.4% |
| DEFEND POSITION | 17.3% |
| DEFEND POSITION URGENTLY | 4.3% |
| ATTACK | 1.0% |

Attacking chances being rare (1%) matches real F1 — most laps, nobody is
within a second of the car ahead. Leader false-ATTACK rate after the fix:
**0/60**.

## 7. Using the engine

```python
from src.strategy.recommend_action import StrategyEngine
import pandas as pd

df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)
real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
engine = StrategyEngine(avg_pit_loss_ms=real_pit_durations.median())

# Pit / DRS / ERS / win probability only (no race-craft):
result = engine.recommend(some_row)

# Full recommendation including race-craft (needs the full field's lap snapshot):
field_df = df[(df["raceId"] == race_id) & (df["lap"] == lap_num)]
result = engine.recommend_full(some_row, same_lap_field_df=field_df)
```