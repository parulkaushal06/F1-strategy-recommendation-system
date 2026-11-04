"""Quantify the 2024 win-model tradeoff from removing position/gap features.

Run from the repository root: python tools/feature_reliance_experiment.py
This is diagnostic only; it does not replace or overwrite production models.
"""
import os
import sys

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score

sys.path.insert(0, ".")
from src.features.train_model import (
    CALIBRATION_YEARS, TEST_YEAR, load_cleaned_dataset, select_feature_columns,
)

POSITION_GAP_FEATURES = {
    "position", "gap_to_leader_s", "gap_per_lap_covered_s", "gap_to_ahead_ms",
}


def evaluate_variant(name, features, splits):
    X_train, y_train = splits["train"]
    X_calib, y_calib = splits["calib"]
    X_test, y_test = splits["test"]
    model = RandomForestClassifier(
        n_estimators=200, max_depth=12, min_samples_leaf=5,
        class_weight="balanced", random_state=42, n_jobs=-1,
    ).fit(X_train[features], y_train)
    calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="isotonic").fit(X_calib[features], y_calib)
    probabilities = calibrated.predict_proba(X_test[features])[:, 1]
    predictions = calibrated.predict(X_test[features])
    return {
        "variant": name,
        "feature_count": len(features),
        "removed_features": ",".join(sorted(set(splits["features"]) - set(features))),
        "roc_auc": roc_auc_score(y_test, probabilities),
        "brier_score": brier_score_loss(y_test, probabilities),
        "log_loss": log_loss(y_test, probabilities),
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
    }


def main():
    df = load_cleaned_dataset()
    features = select_feature_columns(df)
    masks = {
        "train": df.year < min(CALIBRATION_YEARS),
        "calib": df.year.isin(CALIBRATION_YEARS),
        "test": df.year == TEST_YEAR,
    }
    X = df[features].fillna(-999)
    splits = {name: (X.loc[mask], df.loc[mask, "won"]) for name, mask in masks.items()}
    splits["features"] = features
    variants = [
        ("production_all_features", features),
        ("without_current_position", [f for f in features if f != "position"]),
        ("without_position_and_gaps", [f for f in features if f not in POSITION_GAP_FEATURES]),
        ("position_and_gap_features_only", [f for f in features if f in POSITION_GAP_FEATURES]),
    ]
    results = pd.DataFrame(evaluate_variant(name, cols, splits) for name, cols in variants)
    baseline = results.iloc[0]
    results["roc_auc_change_vs_production"] = results.roc_auc - baseline.roc_auc
    results["brier_change_vs_production"] = results.brier_score - baseline.brier_score
    os.makedirs("reports", exist_ok=True)
    results.to_csv("reports/feature_reliance.csv", index=False)
    print(results.to_string(index=False))
    print("Saved reports/feature_reliance.csv; no production model files were changed.")


if __name__ == "__main__":
    main()
