"""
src/features/cross_validate.py

Formal walk-forward cross-validation for the win-probability model, across
multiple independent seasons -- replacing the earlier ad-hoc, manual checks
(re-running train_model.py by hand against 2-3 different test years and
eyeballing the numbers) with a single repeatable script that reports
mean +/- std across every fold.

WHY WALK-FORWARD, NOT RANDOM K-FOLD:
Random k-fold cross-validation would shuffle rows across years, meaning a
model could be "trained" on laps from a 2024 race and tested on a 2020 race
-- using future information to predict the past. That's a form of leakage
specific to time-ordered data, and would make the reported accuracy
unrealistically optimistic (a real deployment would never have 2024 data
available while predicting a 2020 race). Walk-forward validation respects
time order: each fold only ever trains on years strictly before the test
year, matching how the model would actually be used.

Each fold replicates the exact 3-way split used in train_model.py (train /
calibration year / test year) rather than a simpler train/test split, so
these numbers are directly comparable to the production training procedure.

Run from project root, after clean_data.py:
    python src/features/cross_validate.py
"""

import logging
import os
import sys

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score

sys.path.insert(0, ".")
from src.features.train_model import load_cleaned_dataset, select_feature_columns

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MIN_TRAIN_ROWS = 500  # skip a fold if there isn't enough training data to be meaningful
RESULTS_PATH = "reports/cross_validation_results.csv"


def run_one_fold(df: pd.DataFrame, feature_cols: list, test_year: int) -> dict:
    calib_year = test_year - 1

    X = df[feature_cols].fillna(-999)
    y = df["won"]

    train_mask = df["year"] < calib_year
    calib_mask = df["year"] == calib_year
    test_mask = df["year"] == test_year

    X_train, y_train = X[train_mask], y[train_mask]
    X_calib, y_calib = X[calib_mask], y[calib_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    if len(X_train) < MIN_TRAIN_ROWS or len(X_calib) == 0 or len(X_test) == 0:
        logger.info("Skipping test_year=%d (train=%d, calib=%d, test=%d rows -- not enough data)",
                    test_year, len(X_train), len(X_calib), len(X_test))
        return None

    model = RandomForestClassifier(
        n_estimators=200, max_depth=12, min_samples_leaf=5,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train)

    calibrated_model = CalibratedClassifierCV(FrozenEstimator(model), method="isotonic")
    calibrated_model.fit(X_calib, y_calib)

    y_pred = calibrated_model.predict(X_test)
    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]

    result = {
        "test_year": test_year,
        "calib_year": calib_year,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "roc_auc": roc_auc_score(y_test, y_pred_proba),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "brier_score": brier_score_loss(y_test, y_pred_proba),
    }
    logger.info(
        "test_year=%d: ROC-AUC=%.4f precision=%.3f recall=%.3f brier=%.4f (train=%d, test=%d rows)",
        test_year, result["roc_auc"], result["precision"], result["recall"],
        result["brier_score"], len(X_train), len(X_test),
    )
    return result


def cross_validate(min_test_year: int = 2018) -> pd.DataFrame:
    df = load_cleaned_dataset()
    feature_cols = select_feature_columns(df)

    available_years = sorted(df["year"].unique())
    test_years = [y for y in available_years if y >= min_test_year]
    if not test_years:
        raise ValueError(
            f"No years >= min_test_year={min_test_year} found in the dataset "
            f"(years available: {available_years}). Lower min_test_year or check the data."
        )
    logger.info("Running walk-forward cross-validation across test years: %s", test_years)

    results = []
    for test_year in test_years:
        result = run_one_fold(df, feature_cols, test_year)
        if result is not None:
            results.append(result)

    if not results:
        raise RuntimeError(
            "Every fold was skipped (not enough training data). "
            "Lower min_test_year or check the dataset covers enough years."
        )

    results_df = pd.DataFrame(results)

    logger.info("\n%s", results_df.to_string(index=False))

    summary = results_df[["roc_auc", "precision", "recall", "brier_score"]].agg(["mean", "std"])
    logger.info("\n=== Summary across %d folds ===\n%s", len(results_df), summary)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    results_df.to_csv(RESULTS_PATH, index=False)
    logger.info("Saved per-fold results -> %s", RESULTS_PATH)

    return results_df


if __name__ == "__main__":
    try:
        cross_validate()
    except Exception:
        logger.exception("cross_validate.py failed.")
        sys.exit(1)