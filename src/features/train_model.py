"""
src/features/train_model.py

Trains the win-probability model on data/processed/cleaned_dataset.csv and
saves the model + feature column list to models/.

IMPORTANT: this replicates the FINAL training procedure from the end of
notebooks/04_modeling.ipynb, not an earlier draft version. That notebook's
exploration found two real issues, both accounted for below:

1. Calibration: a plain RandomForestClassifier was overconfident (predicted
   ~82% for its top confidence bucket, actual observed win rate only ~47%).
   Fixed with CalibratedClassifierCV(method="isotonic"). An early attempt
   used cv=5 (retraining the model 5 times internally), which caused a ~5x
   slowdown per prediction at inference time. The current approach trains
   the base model ONCE on the training years, then wraps it with
   FrozenEstimator and calibrates ONCE more on a separate calibration year
   -- same calibration quality, far faster at inference.
2. Feature redundancy: gap_to_leader_ms and gap_to_leader_s are the same
   value in two units; gap_to_leader_ms is dropped from the feature set.

This produces THREE files (not one):
  - win_probability_model_calibrated.pkl -- used for every probability
    prediction (the trustworthy, calibrated numbers)
  - win_probability_model_raw.pkl -- the same underlying RandomForest
    before calibration, kept only because CalibratedClassifierCV wraps the
    base estimator and doesn't expose feature_importances_ directly
  - feature_columns.pkl -- the exact feature list both models expect, in order

Run from project root, after clean_data.py:
    python src/features/train_model.py
"""

import logging
import os
import sys

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROCESSED_PATH = "data/processed/cleaned_dataset.csv"
MODELS_DIR = "models"

LEAKAGE_COLS = ["points", "positionOrder", "statusId"]
IDENTIFIER_COLS = ["raceId", "driverId", "driver_number", "session_key", "meeting_key"]
LABEL_COL = "won"
DROPPED_DUPLICATE_FEATURE = "gap_to_leader_ms"  # duplicate of gap_to_leader_s, different units

CALIBRATION_YEAR = 2023
TEST_YEAR = 2024


def load_cleaned_dataset() -> pd.DataFrame:
    if not os.path.exists(PROCESSED_PATH):
        raise FileNotFoundError(
            f"{PROCESSED_PATH} not found. Fix: run `python src/data/clean_data.py` first."
        )
    df = pd.read_csv(PROCESSED_PATH, low_memory=False)
    if df.empty:
        raise ValueError(f"{PROCESSED_PATH} exists but has 0 rows -- re-run clean_data.py.")
    logger.info("Loaded cleaned dataset -> shape: %s", df.shape)
    return df


def select_feature_columns(df: pd.DataFrame) -> list:
    text_cols = df.select_dtypes(include=["object"]).columns.tolist()
    exclude = set(LEAKAGE_COLS + IDENTIFIER_COLS + text_cols + [LABEL_COL])
    feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype != "object"]

    if DROPPED_DUPLICATE_FEATURE in feature_cols:
        feature_cols.remove(DROPPED_DUPLICATE_FEATURE)

    if not feature_cols:
        raise ValueError("No feature columns survived exclusion -- check LEAKAGE_COLS/IDENTIFIER_COLS "
                          "still match real column names in the current dataset.")
    logger.info("%d features selected: %s", len(feature_cols), feature_cols)
    return feature_cols


def three_way_split(df: pd.DataFrame, feature_cols: list):
    """
    Train on years before CALIBRATION_YEAR, calibrate on CALIBRATION_YEAR,
    test on TEST_YEAR. All three must actually exist in the data, or the
    split silently produces an empty set and a confusing downstream error --
    checked explicitly here instead.
    """
    available_years = set(df["year"].unique())
    for label, year in [("CALIBRATION_YEAR", CALIBRATION_YEAR), ("TEST_YEAR", TEST_YEAR)]:
        if year not in available_years:
            raise ValueError(
                f"{label}={year} not present in the dataset (years available: "
                f"{sorted(available_years)}). Update CALIBRATION_YEAR/TEST_YEAR "
                f"in this script to match the data you actually have."
            )

    X = df[feature_cols].fillna(-999)
    y = df[LABEL_COL]

    train_mask = df["year"] < CALIBRATION_YEAR
    calib_mask = df["year"] == CALIBRATION_YEAR
    test_mask = df["year"] == TEST_YEAR

    splits = {
        "train": (X[train_mask], y[train_mask]),
        "calib": (X[calib_mask], y[calib_mask]),
        "test": (X[test_mask], y[test_mask]),
    }
    for name, (X_split, y_split) in splits.items():
        if len(X_split) == 0:
            raise ValueError(f"The '{name}' split has 0 rows -- check the year boundaries above.")
        logger.info("%s: %d rows (%.2f%% won)", name, len(X_split), y_split.mean() * 100)

    return splits


def train() -> dict:
    df = load_cleaned_dataset()
    feature_cols = select_feature_columns(df)
    splits = three_way_split(df, feature_cols)
    X_train, y_train = splits["train"]
    X_calib, y_calib = splits["calib"]
    X_test, y_test = splits["test"]

    logger.info("Training base RandomForestClassifier on training years only...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    logger.info("Calibrating (FrozenEstimator + isotonic, fit once on the calibration year)...")
    calibrated_model = CalibratedClassifierCV(FrozenEstimator(model), method="isotonic")
    calibrated_model.fit(X_calib, y_calib)

    y_pred = calibrated_model.predict(X_test)
    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]

    metrics = {
        "roc_auc": roc_auc_score(y_test, y_pred_proba),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "brier_score": brier_score_loss(y_test, y_pred_proba),
    }
    logger.info("Test-year (%d) metrics: %s", TEST_YEAR, {k: round(v, 4) for k, v in metrics.items()})

    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    logger.info("Top 10 feature importances (from the raw, uncalibrated model):\n%s", importances.head(10))

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(calibrated_model, os.path.join(MODELS_DIR, "win_probability_model_calibrated.pkl"))
    joblib.dump(model, os.path.join(MODELS_DIR, "win_probability_model_raw.pkl"))
    joblib.dump(feature_cols, os.path.join(MODELS_DIR, "feature_columns.pkl"))
    logger.info("Saved win_probability_model_calibrated.pkl, win_probability_model_raw.pkl, "
                "and feature_columns.pkl -> %s", MODELS_DIR)

    return metrics


if __name__ == "__main__":
    try:
        train()
    except Exception:
        logger.exception("train_model.py failed.")
        sys.exit(1)