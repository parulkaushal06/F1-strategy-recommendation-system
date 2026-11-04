"""Focused tests for the optional out-of-sample pit alert integration."""
import pandas as pd

from src.strategy.recommend_action import StrategyEngine


def _row(**overrides):
    values = {
        "pit_stop_this_lap": 0,
        "tire_age_ratio": 0.2,
        "laps_since_last_pit": 10,
        "total_laps": 50,
        "pace_delta_to_fastest_ms": 100,
        "position_change": 0,
    }
    values.update(overrides)
    return pd.Series(values)


def test_optional_pit_model_alert_promotes_next_lap_pit_call():
    engine = StrategyEngine.__new__(StrategyEngine)
    engine.pit_alert = {"threshold": 0.10}
    engine.pit_window_ratio_low = 0.076923
    engine.pit_window_ratio_high = 0.433333
    engine.pit_window_ratio_critical = 0.492958

    result = engine._build_recommendation(_row(), 0.2, 0.15, pit_next_lap_probability=0.14)

    assert result["pit_recommendation"].startswith("PIT NOW")
    assert result["pit_next_lap_probability"] == 0.14


def test_optional_pit_model_does_not_change_win_probability_values():
    engine = StrategyEngine.__new__(StrategyEngine)
    engine.pit_alert = {"threshold": 0.10}
    engine.pit_window_ratio_low = 0.076923
    engine.pit_window_ratio_high = 0.433333
    engine.pit_window_ratio_critical = 0.492958

    result = engine._build_recommendation(_row(), 0.27, 0.19, pit_next_lap_probability=0.14)

    assert result["current_win_probability"] == 27.0
    assert result["model_context_if_pit_now"]["simulated_win_probability"] == 19.0
