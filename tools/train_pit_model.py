"""Train and evaluate a next-lap pit-stop alert without changing the win model.

Run after the cleaned dataset is built:
    python tools/train_pit_model.py

The alert cutoff is selected from expanding-window out-of-fold predictions
through 2020. Seasons 2021-2024 remain untouched for the final OOS evaluation.
"""
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, ".")
from src.strategy.recommend_action import calculate_pit_urgency_score

DATA_PATH = "data/processed/cleaned_dataset.csv"
MODEL_PATH = "models/pit_next_lap_model.pkl"
REPORT_PATH = "reports/pit_oos_evaluation.csv"
TRAIN_END_YEAR = 2020
OOS_START_YEAR = 2021
MIN_ALERT_RECALL = 0.20
MAX_ALERT_FPR = 0.05
PIT_FEATURES = [
    "lap", "position", "grid", "total_laps", "race_progress",
    "cumulative_pit_stops", "laps_since_last_pit", "tire_age_ratio",
    "position_vs_grid", "position_change", "rolling_lap_time_ms",
    "pace_delta_to_fastest_ms", "gap_to_leader_s", "gap_per_lap_covered_s",
    "gap_to_ahead_ms", "drs_zone_proxy", "pit_window_proxy",
    "has_openf1_telemetry", "anomalous_lap_time", "year", "round",
]
MODEL_PARAMS = {
    "max_iter": 140,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 70,
    "l2_regularization": 2.0,
    "class_weight": "balanced",
    "random_state": 42,
}


def prepare_data(path=DATA_PATH):
    df = pd.read_csv(path, low_memory=False)
    required = {"raceId", "driverId", "year", "round", "lap", "pit_stop_this_lap"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    df = df.sort_values(["year", "round", "raceId", "driverId", "lap"]).copy()
    df["next_lap_pit"] = df.groupby(["raceId", "driverId"], sort=False)["pit_stop_this_lap"].shift(-1)
    # Current pit rows and each driver's last observed lap are not decision points.
    df = df[(df["pit_stop_this_lap"] != 1) & df["next_lap_pit"].notna()].copy()
    features = [feature for feature in PIT_FEATURES if feature in df.columns]
    if len(features) != len(PIT_FEATURES):
        missing_features = sorted(set(PIT_FEATURES) - set(features))
        raise ValueError(f"Dataset is missing pit-model features: {missing_features}")
    X = df[features].apply(pd.to_numeric, errors="coerce").fillna(-999)
    y = df["next_lap_pit"].astype(int)
    if y.nunique() != 2:
        raise ValueError("Next-lap pit target must contain both pit and no-pit rows")
    return df.reset_index(drop=True), X.reset_index(drop=True), y.reset_index(drop=True), features


def new_model():
    return HistGradientBoostingClassifier(**MODEL_PARAMS)


def oof_predictions(df, X, y):
    parts = []
    for validation_year in range(2016, TRAIN_END_YEAR + 1):
        train_mask = df["year"] < validation_year
        validation_mask = df["year"] == validation_year
        if not train_mask.any() or not validation_mask.any() or y[train_mask].nunique() != 2:
            continue
        model = new_model().fit(X.loc[train_mask], y.loc[train_mask])
        scores = model.predict_proba(X.loc[validation_mask])[:, 1]
        parts.append(pd.DataFrame({
            "year": df.loc[validation_mask, "year"].to_numpy(),
            "target": y.loc[validation_mask].to_numpy(),
            "score": scores,
        }))
        print(f"OOF validation {validation_year}: {int(validation_mask.sum()):,} rows")
    if not parts:
        raise RuntimeError("No expanding-window OOF predictions could be generated")
    return pd.concat(parts, ignore_index=True)


def select_alert_threshold(target, probabilities):
    candidates = np.unique(np.quantile(probabilities, np.linspace(0.50, 0.9995, 500)))
    valid = []
    negatives = max(1, int((target == 0).sum()))
    for threshold in candidates:
        predicted = probabilities >= threshold
        tp = int((predicted & (target == 1)).sum())
        fp = int((predicted & (target == 0)).sum())
        fn = int((~predicted & (target == 1)).sum())
        recall = tp / max(1, tp + fn)
        fpr = fp / negatives
        precision = tp / max(1, tp + fp)
        if recall >= MIN_ALERT_RECALL and fpr <= MAX_ALERT_FPR:
            valid.append((precision, recall, -fpr, -threshold, float(threshold)))
    if not valid:
        raise RuntimeError(
            "No OOF alert threshold meets the configured minimum recall and maximum FPR. "
            "Review the target/data before relaxing these constraints."
        )
    return max(valid)[-1]


def metric_row(year, label, target, predicted, threshold, **metadata):
    target = np.asarray(target, dtype=bool)
    predicted = np.asarray(predicted, dtype=bool)
    tp = int((target & predicted).sum())
    fp = int((~target & predicted).sum())
    tn = int((~target & ~predicted).sum())
    fn = int((target & ~predicted).sum())
    return {
        "year": year, "method": label, "rows": len(target), "tp": tp, "fp": fp,
        "tn": tn, "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "specificity": tn / (tn + fp) if tn + fp else 0.0,
        "alert_threshold": threshold, **metadata,
    }


def main():
    df, X, y, features = prepare_data()
    oof = oof_predictions(df, X, y)
    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    oof_probabilities = calibrator.fit_transform(oof["score"], oof["target"])
    threshold = select_alert_threshold(oof["target"].to_numpy(), oof_probabilities)
    validation_rows = metric_row(
        "2016-2020 OOF", "pit_classifier", oof["target"],
        oof_probabilities >= threshold, threshold,
        model_features=len(features), min_recall_constraint=MIN_ALERT_RECALL,
        max_fpr_constraint=MAX_ALERT_FPR,
    )

    train_mask = df["year"] <= TRAIN_END_YEAR
    test_mask = df["year"] >= OOS_START_YEAR
    model = new_model().fit(X.loc[train_mask], y.loc[train_mask])
    raw_scores = model.predict_proba(X.loc[test_mask])[:, 1]
    test_probabilities = calibrator.predict(raw_scores)
    test_frame = df.loc[test_mask].copy()
    test_frame["pit_classifier_prediction"] = test_probabilities >= threshold

    # Keep the transparent urgency rule as a comparator. Its tire-window
    # quantiles use training-era pre-pit observations only.
    training_mask = df["year"] <= TRAIN_END_YEAR
    training_pit = df[training_mask & (y == 1)]
    ratios = training_pit["tire_age_ratio"].dropna()
    low, high, critical = ratios.quantile([0.10, 0.90, 0.95]).tolist()
    test_frame["heuristic_score"] = test_frame.apply(
        lambda row: calculate_pit_urgency_score(row, float(row["tire_age_ratio"]), low, high, critical),
        axis=1,
    )
    target = y.loc[test_mask].to_numpy(dtype=bool)
    rows = [validation_rows]
    for year, group in [*(test_frame.groupby("year", sort=True)), ("ALL", test_frame)]:
        idx = group.index
        group_target = y.loc[idx].to_numpy(dtype=bool)
        group_probabilities = test_probabilities[test_frame.index.get_indexer(idx)]
        rows.append(metric_row(
            year, "pit_classifier", group_target, group_probabilities >= threshold, threshold,
            model_features=len(features), training_end_year=TRAIN_END_YEAR,
        ))
        for cutoff, label in ((40, "heuristic_consider_or_pit_now"), (70, "heuristic_pit_now")):
            rows.append(metric_row(
                year, label, group_target, group["heuristic_score"].to_numpy() >= cutoff, cutoff,
                train_ratio_q10=low, train_ratio_q90=high, train_ratio_q95=critical,
            ))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    joblib.dump({"model": model, "calibrator": calibrator, "features": features,
                 "threshold": threshold, "train_end_year": TRAIN_END_YEAR}, MODEL_PATH)
    report = pd.DataFrame(rows)
    report.to_csv(REPORT_PATH, index=False)
    print(f"OOF-selected pit alert threshold: {threshold:.6f}")
    print(report.to_string(index=False))
    print(f"Saved {MODEL_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
