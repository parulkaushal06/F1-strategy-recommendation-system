"""Compare sentinel handling strategies on the production temporal split.

Run from the repository root: python tools/feature_ablation.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, ".")
from src.features.train_model import (CALIBRATION_YEARS, TEST_YEAR, load_cleaned_dataset,
                                      select_feature_columns)


def expected_calibration_error(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total = len(y)
    error = 0.0
    for i in range(bins):
        mask = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= edges[i + 1]))
        if mask.any():
            error += mask.sum() / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return error


def fit_evaluate(name, X_train, y_train, X_calib, y_calib, X_test, y_test):
    model = RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=5,
                                   class_weight="balanced", random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    calibrated = CalibratedClassifierCV(FrozenEstimator(model), method="isotonic")
    calibrated.fit(X_calib, y_calib)
    p = calibrated.predict_proba(X_test)[:, 1]
    return {"variant": name, "feature_count": X_train.shape[1],
            "roc_auc": roc_auc_score(y_test, p), "brier_score": brier_score_loss(y_test, p),
            "log_loss": log_loss(y_test, p), "ece_10_bins": expected_calibration_error(y_test.to_numpy(), p)}


def main():
    df = load_cleaned_dataset()
    features = select_feature_columns(df)
    train_mask = df.year < min(CALIBRATION_YEARS)
    calib_mask = df.year.isin(CALIBRATION_YEARS)
    test_mask = df.year == TEST_YEAR
    y_train, y_calib, y_test = df.loc[train_mask, "won"], df.loc[calib_mask, "won"], df.loc[test_mask, "won"]
    raw = df[features].apply(pd.to_numeric, errors="coerce")
    missing_columns = [c for c in features if raw.loc[train_mask, c].isna().any()]

    # Production baseline: every feature retained, NaN represented by sentinel -999.
    baseline = fit_evaluate("sentinel_-999_all_features", raw.loc[train_mask].fillna(-999), y_train,
                            raw.loc[calib_mask].fillna(-999), y_calib,
                            raw.loc[test_mask].fillna(-999), y_test)

    # Ablate all columns with missing values in training data; selection uses train only.
    retained = [c for c in features if c not in missing_columns]
    ablated = fit_evaluate("drop_train_missing_features", raw.loc[train_mask, retained], y_train,
                           raw.loc[calib_mask, retained], y_calib,
                           raw.loc[test_mask, retained], y_test)

    # Median imputation with explicit missing indicators; all-empty train columns
    # use -999 and are omitted from this variant to avoid a non-learned median.
    usable = [c for c in features if not raw.loc[train_mask, c].isna().all()]
    medians = raw.loc[train_mask, usable].median()
    def with_indicators(mask):
        values = raw.loc[mask, usable]
        return pd.concat([values.fillna(medians), values.isna().astype("int8").add_suffix("__missing")], axis=1)
    median = fit_evaluate("train_median_plus_missing_indicators", with_indicators(train_mask), y_train,
                          with_indicators(calib_mask), y_calib, with_indicators(test_mask), y_test)

    result = pd.DataFrame([baseline, ablated, median])
    result["train_missing_feature_count"] = len(missing_columns)
    result["train_missing_features"] = ",".join(missing_columns)
    os.makedirs("reports", exist_ok=True)
    result.to_csv("reports/feature_ablation.csv", index=False)
    print(result.to_string(index=False))
    print("Saved reports/feature_ablation.csv")


if __name__ == "__main__":
    main()
