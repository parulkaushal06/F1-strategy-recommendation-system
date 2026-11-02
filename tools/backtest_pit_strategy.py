"""
backtest_pit_strategy.py

So far, the pit-stop recommendation has only been validated on WHETHER it
correctly flags a pit as due (73% recall, 0.7% false positive rate -- see
docs/10_strategy_engine.md). That answers "does it recognize the right
lap?", not "does following its window actually correlate with a better
result?" -- a genuinely different, more important question for a strategy
tool. This script answers the second question directly, using real
historical outcomes.

METHOD:
For every driver with exactly one real pit stop in a race (single-stop
strategies are the cleanest to analyze -- multi-stop races have compounding
decisions that are harder to attribute to one pit call), check whether
their real pit lap fell inside the engine's recommended tire-age-ratio
window (PIT_WINDOW_RATIO_LOW to PIT_WINDOW_RATIO_HIGH). Then compare
outcomes between the "pitted inside the window" group and the "pitted
outside it" group.

HONEST CONFOUND, stated up front: this is a correlational check, not a
controlled experiment. Front-running drivers and back-markers often pit at
systematically different times for reasons unrelated to tire strategy
(track position, undercut/overcut games, team orders). To reduce that
confound, the primary comparison uses POSITIONS GAINED (position_vs_grid:
finishing position vs starting grid) rather than raw finishing position,
and results are also broken down by starting grid quartile.

Run from project root:
    python backtest_pit_strategy.py
"""
import sys

import pandas as pd

sys.path.insert(0, ".")
from src.strategy.recommend_action import PIT_WINDOW_RATIO_HIGH, PIT_WINDOW_RATIO_LOW

CLEANED_PATH = "data/processed/cleaned_dataset.csv"


def main():
    df = pd.read_csv(CLEANED_PATH, low_memory=False)

    # One row per (raceId, driverId): their final result + their single pit lap, if any.
    pit_laps = df[df["pit_stop_this_lap"] == 1].groupby(["raceId", "driverId"]).agg(
        n_pit_stops=("lap", "count"),
        pit_lap=("lap", "first"),
    ).reset_index()

    single_stop = pit_laps[pit_laps["n_pit_stops"] == 1].copy()
    print(f"Single-stop driver-races found: {len(single_stop)}")

    race_info = df[["raceId", "driverId", "total_laps", "grid", "positionOrder", "position_vs_grid", "won"]].drop_duplicates(
        subset=["raceId", "driverId"]
    )
    merged = single_stop.merge(race_info, on=["raceId", "driverId"], how="left")
    merged["pit_ratio"] = merged["pit_lap"] / merged["total_laps"]
    merged["in_recommended_window"] = merged["pit_ratio"].between(
        PIT_WINDOW_RATIO_LOW, PIT_WINDOW_RATIO_HIGH
    )

    print(f"Recommended window: {PIT_WINDOW_RATIO_LOW} - {PIT_WINDOW_RATIO_HIGH} (tire age ratio)")
    print(f"Pitted INSIDE window: {merged['in_recommended_window'].sum()}")
    print(f"Pitted OUTSIDE window: {(~merged['in_recommended_window']).sum()}")

    print("\n=== Overall comparison ===")
    summary = merged.groupby("in_recommended_window").agg(
        avg_positions_gained=("position_vs_grid", "mean"),
        avg_finish_position=("positionOrder", "mean"),
        win_rate_pct=("won", lambda x: x.mean() * 100),
        n=("raceId", "count"),
    )
    print(summary)

    print("\n=== Same comparison, split by starting grid quartile ===")
    print("(controls for the confound that front-runners and back-markers pit differently)")
    merged["grid_quartile"] = pd.qcut(merged["grid"], 4, labels=["Q1 (front)", "Q2", "Q3", "Q4 (back)"])
    by_quartile = merged.groupby(["grid_quartile", "in_recommended_window"], observed=True).agg(
        avg_positions_gained=("position_vs_grid", "mean"),
        avg_finish_position=("positionOrder", "mean"),
        n=("raceId", "count"),
    )
    print(by_quartile)


if __name__ == "__main__":
    main()