"""Evaluate the production pit-urgency rule on future seasons.

Run from the repository root: python tools/evaluate_pit_oos.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, ".")
from src.strategy.recommend_action import calculate_pit_urgency_score

DATA_PATH = "data/processed/cleaned_dataset.csv"
OUTPUT_PATH = "reports/pit_oos_evaluation.csv"
TRAIN_END_YEAR = 2020
ALERT_THRESHOLDS = ((40, "consider_or_pit_now"), (70, "pit_now"))


def main():
    df = pd.read_csv(DATA_PATH, low_memory=False)
    required = {"raceId", "driverId", "year", "lap", "pit_stop_this_lap", "tire_age_ratio", "won"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    df = df.sort_values(["raceId", "driverId", "lap"]).copy()
    groups = df.groupby(["raceId", "driverId"], sort=False)
    df["next_lap_pit"] = groups["pit_stop_this_lap"].shift(-1)
    training_pit_rows = df[(df.year <= TRAIN_END_YEAR) & (df.next_lap_pit == 1)]
    ratios = training_pit_rows.tire_age_ratio.dropna()
    if ratios.empty:
        raise ValueError("No pre-pit tire-age samples exist through 2020")
    low, high, critical = ratios.quantile([.10, .90, .95]).tolist()
    print(f"Train-only thresholds (pre-pit tire_age_ratio q10/q90/q95): {low:.5f}, {high:.5f}, {critical:.5f}")

    test = df[(df.year > TRAIN_END_YEAR) & df.next_lap_pit.notna() & (df.pit_stop_this_lap != 1)].copy()
    test["score"] = test.apply(
        lambda r: calculate_pit_urgency_score(r, float(r.tire_age_ratio), low, high, critical), axis=1
    )
    test["actual_pit"] = test.next_lap_pit.astype(int) == 1
    rows = []
    for threshold, level in ALERT_THRESHOLDS:
        test["predicted_pit"] = test.score >= threshold
        for year, part in [*(test.groupby("year")), ("ALL", test)]:
            tp = int((part.predicted_pit & part.actual_pit).sum())
            fp = int((part.predicted_pit & ~part.actual_pit).sum())
            tn = int((~part.predicted_pit & ~part.actual_pit).sum())
            fn = int((~part.predicted_pit & part.actual_pit).sum())
            rows.append({"year": year, "recommendation_level": level, "rows": len(part), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
                         "precision": tp / (tp + fp) if tp + fp else 0.0,
                         "recall": tp / (tp + fn) if tp + fn else 0.0,
                         "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
                         "specificity": tn / (tn + fp) if tn + fp else 0.0,
                         "alert_score_threshold": threshold,
                         "train_threshold_low": low, "train_threshold_high": high,
                         "train_threshold_critical": critical})
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_PATH, index=False)
    print(result.to_string(index=False))
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
