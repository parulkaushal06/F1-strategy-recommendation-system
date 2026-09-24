"""
tests/test_strategy_engine.py

Turns the manual validation we did by hand (in chat, against the real
dataset) into permanent, automated regression tests -- most importantly the
two real bugs that were found and fixed:

1. The tire-age reset bug (laps_since_last_pit was 0 on every real pit-stop
   row) -- see docs/10_strategy_engine.md section 3.1.
2. The race-leader false-ATTACK bug (gap_to_ahead_ms == 0 for the leader is
   a data artifact, not a real zero-gap reading) -- see section 6.3.

These run against tiny hand-built rows (not the full dataset), so they're
fast and don't depend on the data pipeline having been run.
"""
import pandas as pd
import pytest

from src.strategy.recommend_action import StrategyEngine


@pytest.fixture(scope="module")
def engine(synthetic_env):
    return StrategyEngine(
        model_path=synthetic_env["RACECRAFT_MODEL_PATH"],
        features_path=synthetic_env["RACECRAFT_FEATURES_PATH"],
        avg_pit_loss_ms=22000,
    )


def _make_row(**overrides):
    base = {
        "raceId": 1, "driverId": 1, "lap": 20, "position": 5, "grid": 5,
        "gap_to_leader_ms": 5000, "gap_to_leader_s": 5.0, "gap_per_lap_covered_s": 0.25,
        "gap_to_ahead_ms": 1500.0, "cum_time_ms": 1_800_000,
        "pit_stop_this_lap": 0, "cumulative_pit_stops": 1,
        "laps_since_last_pit": 12, "tire_age_ratio": 0.24,
        "drs_zone_proxy": 0, "pace_delta_to_fastest_ms": 200,
        "rolling_lap_time_ms": 91000, "position_change": 0,
        "total_laps": 50,
    }
    base.update(overrides)
    return pd.Series(base)


def test_pit_stop_row_returns_na_not_a_misleading_recommendation(engine):
    """Regression test for the tire-age reset bug: a row where a pit stop
    is already happening this lap must return N/A, not silently use the
    post-pit (near-zero) tire age as if it were a real 'should I pit' signal."""
    row = _make_row(pit_stop_this_lap=1, laps_since_last_pit=0, tire_age_ratio=0.0)
    result = engine.recommend(row)
    assert "N/A" in result["pit_recommendation"]


def test_fresh_tires_recommend_stay_out(engine):
    row = _make_row(laps_since_last_pit=2, tire_age_ratio=0.04)
    result = engine.recommend(row)
    assert "STAY OUT" in result["pit_recommendation"]


def test_very_old_tires_recommend_pit_now(engine):
    row = _make_row(laps_since_last_pit=45, tire_age_ratio=0.90)
    result = engine.recommend(row)
    assert "PIT NOW" in result["pit_recommendation"]


def test_race_leader_never_gets_a_false_attack_call(engine):
    """
    Regression test for the leader edge-case bug: gap_to_ahead_ms == 0 for
    the leader is a data artifact (nothing to diff against), not a real
    "car right in front of you" reading, and must not trigger ATTACK just
    because the leader also has good pace.
    """
    leader_row = _make_row(position=1, gap_to_ahead_ms=0.0, pace_delta_to_fastest_ms=0)
    field_df = pd.DataFrame([
        _make_row(driverId=1, position=1, gap_to_ahead_ms=0.0, pace_delta_to_fastest_ms=0),
        _make_row(driverId=2, position=2, gap_to_ahead_ms=2500.0),
    ])
    result = engine.recommend_full(leader_row, same_lap_field_df=field_df)
    assert "ATTACK" not in result["race_craft_recommendation"]


def test_gap_to_behind_detects_a_car_within_drs_range(engine):
    field_df = pd.DataFrame([
        _make_row(driverId=1, position=1, gap_to_leader_ms=0.0),
        _make_row(driverId=2, position=2, gap_to_leader_ms=800.0),  # right behind, within DRS range
    ])
    gap_behind = StrategyEngine.compute_gap_to_behind_ms(field_df, driver_id=1)
    assert gap_behind == pytest.approx(800.0)


def test_last_car_on_track_has_no_gap_to_behind(engine):
    field_df = pd.DataFrame([
        _make_row(driverId=1, position=1),
        _make_row(driverId=2, position=2),
    ])
    gap_behind = StrategyEngine.compute_gap_to_behind_ms(field_df, driver_id=2)
    assert gap_behind is None


def test_ers_overtake_only_recommended_in_drs_range_and_off_pace(engine):
    in_range_off_pace = _make_row(drs_zone_proxy=1, pace_delta_to_fastest_ms=500)
    result = engine.recommend(in_range_off_pace)
    assert "OVERTAKE" in result["ers_recommendation"]

    in_range_on_pace = _make_row(drs_zone_proxy=1, pace_delta_to_fastest_ms=10)
    result = engine.recommend(in_range_on_pace)
    assert "OVERTAKE" not in result["ers_recommendation"]