"""
src/strategy/recommend_action.py

Strategy Recommendation Engine.

Core idea: we already have a trained model that predicts win probability from a
race-state row. We ask the model a what-if question (simulate pitting this lap,
compare win probability before/after) for CONTEXT, but the primary pit decision
uses a data-driven tire-age window, for the reasons documented in the design
note inside `recommend()`.

--------------------------------------------------------------------------
BUG FIX (see docs/10_strategy_engine.md for full write-up):

The original version of this engine used a FIXED absolute-lap pit window
(laps_since_last_pit between 15-30). Two problems with that:

1. `laps_since_last_pit` is computed upstream in `src/data/merge_datasets.py`
   and resets to 0 on the SAME row a pit stop happens, not the row after.
   That means every real pit-stop row in the training data has
   laps_since_last_pit == 0 (verified: 11,371/11,371 real pit stops, 100%).
   So testing the engine against real pit-stop rows always fails the
   15-30 window check -- not because the recommendation logic is wrong in
   principle, but because the feature it reads has already been zeroed by
   the very event it's trying to detect.
2. A fixed lap-count window doesn't scale with race length (a 78-lap race
   and a 53-lap race shouldn't share the same "15-30 laps" window).

This version fixes both:
- Uses `tire_age_ratio` (laps_since_last_pit / total_laps) instead of a fixed
  lap count, with default thresholds derived empirically from real pit-stop
  timing in the dataset (see PIT_WINDOW_RATIO_LOW/HIGH below).
- Replaces the single if/elif cliff with a continuous 0-100 pit urgency
  score blending tire age, pace degradation, and position trend, so the
  recommendation doesn't collapse to "STAY OUT" just because one binary
  flag didn't fire.
- Explicitly flags rows where `pit_stop_this_lap == 1` is already set in the
  input, since (per the bug above) `laps_since_last_pit` on such a row is
  NOT meaningful tire age -- it's post-pit state, not a decision point.

The permanent fix for the ROOT cause (so future retraining doesn't inherit
the same mislabeled feature) is in `merge_datasets.py`: shift the counter
reset so a pit lap records the tire age it had BEFORE pitting, then resets
for the next lap. See that file's `laps_since_pit()` function.
--------------------------------------------------------------------------

Usage:
    from src.strategy.recommend_action import StrategyEngine
    engine = StrategyEngine()
    result = engine.recommend(current_row)
"""

import joblib
import pandas as pd
import numpy as np
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models", "win_probability_model.pkl")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models", "feature_columns.pkl")

# Empirically derived from real pit-stop timing in cleaned_dataset.csv:
# tire_age_ratio at the lap BEFORE a real pit stop has median 0.257, with the
# middle 80% falling between the 10th and 90th percentiles below. Used as the
# default "typical pit window" instead of a fixed lap count.
PIT_WINDOW_RATIO_LOW = 0.12
PIT_WINDOW_RATIO_HIGH = 0.45
PIT_WINDOW_RATIO_CRITICAL = 0.55  # beyond this, tires are well past typical stop timing


class StrategyEngine:
    def __init__(self, model_path=MODEL_PATH, features_path=FEATURES_PATH,
                 avg_pit_loss_ms=None, fresh_tire_pace_gain_ms=None,
                 degradation_ms_per_lap=70,
                 pit_window_ratio_low=PIT_WINDOW_RATIO_LOW,
                 pit_window_ratio_high=PIT_WINDOW_RATIO_HIGH,
                 pit_window_ratio_critical=PIT_WINDOW_RATIO_CRITICAL):
        self.model = joblib.load(model_path)
        self.feature_cols = joblib.load(features_path)
        self.avg_pit_loss_ms = avg_pit_loss_ms
        self.fresh_tire_pace_gain_ms = fresh_tire_pace_gain_ms
        self.degradation_ms_per_lap = degradation_ms_per_lap
        self.pit_window_ratio_low = pit_window_ratio_low
        self.pit_window_ratio_high = pit_window_ratio_high
        self.pit_window_ratio_critical = pit_window_ratio_critical

    def _predict_proba(self, row_df):
        """Run the model on a single-row DataFrame, return win probability (0-1)."""
        X = row_df[self.feature_cols].fillna(-999)
        return self.model.predict_proba(X)[:, 1][0]

    def _pace_gain_for_row(self, row):
        if self.fresh_tire_pace_gain_ms is not None:
            return self.fresh_tire_pace_gain_ms
        tire_age_laps = min(row.get("laps_since_last_pit", 0), 20)  # cap at 20 laps
        return tire_age_laps * self.degradation_ms_per_lap

    def simulate_pit_now(self, row):
        """
        Return a copy of `row` as if the driver pitted THIS lap:
        - pit_stop_this_lap = 1
        - laps_since_last_pit resets to 0
        - tire_age_ratio resets to 0
        - cumulative_pit_stops += 1
        - gap_to_leader increases by the real median pit stop time cost (the cost)
        - pace_delta_to_fastest_ms / rolling_lap_time_ms improve, scaled to how
          worn the CURRENT tires are (the benefit).
        """
        sim = row.copy()
        sim["pit_stop_this_lap"] = 1
        sim["laps_since_last_pit"] = 0
        sim["tire_age_ratio"] = 0.0
        sim["cumulative_pit_stops"] = row.get("cumulative_pit_stops", 0) + 1

        pit_cost_ms = self.avg_pit_loss_ms if self.avg_pit_loss_ms is not None else 22000
        sim["gap_to_leader_ms"] = row.get("gap_to_leader_ms", 0) + pit_cost_ms
        sim["gap_to_leader_s"] = sim["gap_to_leader_ms"] / 1000.0
        sim["gap_to_ahead_ms"] = row.get("gap_to_ahead_ms", 0) + pit_cost_ms
        sim["cum_time_ms"] = row.get("cum_time_ms", 0) + pit_cost_ms

        pace_gain_ms = self._pace_gain_for_row(row)
        if "pace_delta_to_fastest_ms" in sim:
            sim["pace_delta_to_fastest_ms"] = max(0, row.get("pace_delta_to_fastest_ms", 0) - pace_gain_ms)
        if "rolling_lap_time_ms" in sim:
            sim["rolling_lap_time_ms"] = max(0, row.get("rolling_lap_time_ms", 0) - pace_gain_ms)

        return sim

    def _tire_age_ratio(self, row):
        """Prefer the precomputed column; fall back to computing it if missing."""
        if "tire_age_ratio" in row and pd.notna(row.get("tire_age_ratio")):
            return float(row["tire_age_ratio"])
        laps_on_tire = row.get("laps_since_last_pit", 0)
        total_laps = row.get("total_laps", None)
        if total_laps:
            return float(laps_on_tire) / float(total_laps)
        return 0.0

    def _pit_urgency_score(self, row, tire_age_ratio):
        """
        Continuous 0-100 "how much does this driver need to pit" score, so the
        recommendation doesn't hinge on a single binary flag. Blends:
          - tire age ratio (primary signal, ramps up through the pit window)
          - pace degradation vs the fastest lap this round (losing time = bad tires)
          - recent position trend (losing places recently supports pitting)
        Each component is weighted; weights are simple and documented, not fit --
        this is a transparent heuristic, not a second ML model.
        """
        # --- Tire age component (0-70 points) ---
        low, high, crit = self.pit_window_ratio_low, self.pit_window_ratio_high, self.pit_window_ratio_critical
        if tire_age_ratio <= low:
            tire_component = 70 * (tire_age_ratio / low) * 0.3  # still fresh, low urgency
        elif tire_age_ratio <= high:
            # ramps from 21 to 70 across the main window
            tire_component = 21 + 49 * (tire_age_ratio - low) / (high - low)
        elif tire_age_ratio <= crit:
            tire_component = 70 + 20 * (tire_age_ratio - high) / (crit - high)
        else:
            tire_component = 90 + min(10, (tire_age_ratio - crit) * 20)
        tire_component = max(0, min(100, tire_component))

        # --- Pace degradation component (0-20 points) ---
        pace_delta = row.get("pace_delta_to_fastest_ms", 0) or 0
        # 0ms delta -> 0 points; >= 1500ms behind fastest -> full 20 points
        pace_component = max(0, min(20, (pace_delta / 1500.0) * 20))

        # --- Position trend component (0-10 points) ---
        position_change = row.get("position_change", 0) or 0
        # losing places recently (position_change < 0 means position number went up)
        trend_component = 10 if position_change < 0 else 0

        # Weighted combination (tire age dominates, capped at 100):
        score = min(100, tire_component * 0.7 + pace_component + trend_component)
        return round(float(score), 1)

    def recommend(self, row):
        """
        row: a pandas Series or single-row DataFrame representing the CURRENT
             race state for one driver (must contain all feature_cols).
        Returns a dict with win probability, pit recommendation, and DRS flag.

        DESIGN NOTE: an earlier version tried to decide "pit or not" purely from
        the model's simulated win-probability delta. Testing showed this was
        structurally biased toward always recommending "STAY OUT" -- the trained
        model weights position/gap features far more heavily than tire-age
        features (see docs/09_model_results.md), so no realistic simulated tire
        benefit could ever outweigh the real time cost of a pit stop in that
        delta. This version's PRIMARY decision instead comes from a data-driven
        pit urgency score (see `_pit_urgency_score`), with the model's win
        probability numbers shown as supporting context, not the sole driver.
        """
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        current_df = pd.DataFrame([row])
        current_win_prob = self._predict_proba(current_df)

        # --- Pit simulation (context, not the decision itself) ---
        sim_row = self.simulate_pit_now(row)
        sim_df = pd.DataFrame([sim_row])
        sim_win_prob = self._predict_proba(sim_df)
        pit_gain = sim_win_prob - current_win_prob

        # --- Primary pit decision: data-driven tire-age-ratio window + urgency score ---
        tire_age_ratio = self._tire_age_ratio(row)
        laps_on_tire = row.get("laps_since_last_pit", 0)
        urgency = self._pit_urgency_score(row, tire_age_ratio)

        # Flag (don't silently mis-answer) the known edge case: if this row IS
        # the lap a pit stop actually happened on, laps_since_last_pit/tire_age_ratio
        # are post-pit values (~0), not a meaningful "should I pit" input.
        already_pitting_this_lap = bool(row.get("pit_stop_this_lap", 0) == 1)

        if already_pitting_this_lap:
            pit_recommendation = "N/A (this row already shows a pit stop happening this lap)"
        elif urgency >= 70:
            pit_recommendation = "PIT NOW (tires well past typical window)"
        elif urgency >= 40:
            pit_recommendation = "CONSIDER PIT (tires in typical pit window)"
        else:
            pit_recommendation = "STAY OUT (tires still fresh)"

        # --- DRS recommendation (using the existing engineered proxy feature) ---
        drs_available = bool(row.get("drs_zone_proxy", 0) == 1)

        # --- ERS recommendation (proxy only -- see docs/06_known_limitations.md) ---
        # No public data source (including OpenF1) exposes real ERS deployment mode,
        # so this is inferred, not measured: recommend "Overtake Mode" only when
        # BOTH a real overtaking opportunity exists (within DRS range) AND the
        # driver is meaningfully off the pace (would benefit from the extra power),
        # since ERS's main strategic use is closing/completing a pass, not general cruising.
        pace_delta = row.get("pace_delta_to_fastest_ms", 0) or 0
        ers_overtake_recommended = bool(drs_available and pace_delta > 300)
        if ers_overtake_recommended:
            ers_recommendation = "USE ERS OVERTAKE MODE (proxy: DRS range + off race pace)"
        else:
            ers_recommendation = "STANDARD ERS DEPLOYMENT (proxy)"

        return {
            "current_win_probability": round(float(current_win_prob) * 100, 2),
            "pit_recommendation": pit_recommendation,
            "pit_urgency_score": urgency,
            "tire_age_ratio": round(tire_age_ratio, 3),
            "laps_on_current_tires": int(laps_on_tire),
            "ers_recommendation": ers_recommendation,
            "model_context_if_pit_now": {
                "simulated_win_probability": round(float(sim_win_prob) * 100, 2),
                "probability_change": round(float(pit_gain) * 100, 2),
                "note": "reflects the real time cost of pitting; not the sole basis for the recommendation above — see design note in recommend()"
            },
            "drs_recommendation": "DRS AVAILABLE" if drs_available else "NO DRS",
        }

    @staticmethod
    def compute_gap_to_behind_ms(same_lap_field_df, driver_id, position_col="position",
                                  gap_col="gap_to_leader_ms", driver_id_col="driverId"):
        """
        Race-craft recommendations (attack/defend/manage pace) need to know how
        close the car BEHIND is -- a signal the dataset never stored, because
        `gap_to_ahead_ms` only looks forward. This can't be computed from a
        single driver's row in isolation; it needs the full field's state on
        that lap (every car's gap_to_leader_ms for that raceId+lap).

        same_lap_field_df: DataFrame of ALL drivers' rows for the SAME raceId
                            and lap as the driver being evaluated (in live use,
                            this is just "the current lap's timing sheet").
        Returns gap_to_behind_ms (float), or None if this driver is last on track.
        """
        field = same_lap_field_df.sort_values(position_col).reset_index(drop=True)
        idx_list = field.index[field[driver_id_col] == driver_id].tolist()
        if not idx_list:
            return None
        idx = idx_list[0]
        if idx + 1 >= len(field):
            return None  # last car on track, nobody behind
        return float(field.loc[idx + 1, gap_col] - field.loc[idx, gap_col])

    def recommend_full(self, row, same_lap_field_df=None):
        """
        Full strategy recommendation: everything from recommend() PLUS a
        race-craft call (attack / defend / manage pace) using signals that
        were already engineered in the dataset but previously unused for
        recommendations: gap_to_ahead_ms, gap_to_behind_ms (computed here),
        pace_delta_to_fastest_ms, and position_change.

        same_lap_field_df: optional full-field snapshot for this raceId+lap
            (see compute_gap_to_behind_ms). If not provided, defend/attack
            logic falls back to gap_to_ahead-only reasoning and gap_to_behind
            is reported as unknown.
        """
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        result = self.recommend(row)

        gap_ahead = row.get("gap_to_ahead_ms", None)
        # Data artifact: the leader (position 1) always has gap_to_ahead_ms == 0
        # in the dataset (nothing to diff against), which is NOT a real "car
        # right in front of you" reading. Treat it as "nobody ahead" so the
        # leader doesn't get a false "ATTACK" call every time they also have
        # good pace (which, being the leader, they usually do).
        if row.get("position", None) == 1:
            gap_ahead = None

        gap_behind = None
        if same_lap_field_df is not None:
            gap_behind = self.compute_gap_to_behind_ms(same_lap_field_df, row.get("driverId"))

        pace_delta = row.get("pace_delta_to_fastest_ms", 0) or 0
        losing_places = (row.get("position_change", 0) or 0) < 0

        DRS_THRESHOLD_MS = 1000  # matches drs_zone_proxy's own definition

        under_attack = gap_behind is not None and gap_behind <= DRS_THRESHOLD_MS
        attacking_chance = gap_ahead is not None and gap_ahead <= DRS_THRESHOLD_MS and pace_delta < 300
        comfortable = (gap_behind is None or gap_behind > 2 * DRS_THRESHOLD_MS) and \
                      (gap_ahead is None or gap_ahead > 2 * DRS_THRESHOLD_MS)

        if under_attack and not attacking_chance:
            race_craft = "DEFEND POSITION (car behind is within DRS range)"
            if losing_places:
                race_craft = "DEFEND POSITION URGENTLY (car behind in range, already losing places)"
        elif attacking_chance:
            race_craft = "ATTACK (car ahead in range and you have the pace to pass)"
        elif comfortable:
            race_craft = "MANAGE PACE (no immediate threat or chance — protect tires/engine)"
        else:
            race_craft = "HOLD STATION (no clear attack/defend trigger right now)"

        result["gap_to_ahead_ms"] = gap_ahead
        result["gap_to_behind_ms"] = gap_behind
        result["race_craft_recommendation"] = race_craft
        return result


if __name__ == "__main__":
    # Quick manual test using real rows from the cleaned dataset
    df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)

    real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
    avg_pit_loss_ms = real_pit_durations.median() if len(real_pit_durations) > 0 else 22000
    print(f"Median real pit stop cost from data: {avg_pit_loss_ms:.0f} ms "
          f"({avg_pit_loss_ms/1000:.1f} seconds), from {len(real_pit_durations)} real pit stops")

    ESTIMATED_DEGRADATION_MS_PER_LAP = 70
    engine = StrategyEngine(avg_pit_loss_ms=avg_pit_loss_ms, fresh_tire_pace_gain_ms=None)

    print("\n=== Test 1: a few random rows ===")
    random_sample = df.sample(5, random_state=1)
    for _, row in random_sample.iterrows():
        result = engine.recommend(row)
        print(f"race={row['raceId']} driver={row['driverId']} lap={row['lap']} "
              f"grid={row['grid']} position={row['position']} -> {result['pit_recommendation']} "
              f"(urgency={result['pit_urgency_score']}, tire_age_ratio={result['tire_age_ratio']})")

    print("\n=== Test 2: rows the LAP BEFORE a real pit stop actually happened ===")
    # (Using the lap before, since the pit-lap row itself has post-pit tire age -- see design note.)
    df_sorted = df.sort_values(["raceId", "driverId", "lap"])
    df_sorted["next_lap_is_pit"] = df_sorted.groupby(["raceId", "driverId"])["pit_stop_this_lap"].shift(-1)
    pre_pit_rows = df_sorted[df_sorted["next_lap_is_pit"] == 1].sample(8, random_state=1)
    correct = 0
    for _, row in pre_pit_rows.iterrows():
        result = engine.recommend(row)
        flagged = "PIT" in result["pit_recommendation"]
        correct += flagged
        print(f"race={row['raceId']} driver={row['driverId']} lap={row['lap']} "
              f"tire_age_ratio={result['tire_age_ratio']} -> {result['pit_recommendation']} "
              f"(driver pit on the NEXT lap in reality)")
    print(f"\n{correct}/8 correctly flagged a pit as due, on the lap right before a real pit stop.")