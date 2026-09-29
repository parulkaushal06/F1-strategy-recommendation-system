"""
src/features/explain.py

Turns the SHAP exploration done in notebooks/04_modeling.ipynb (cells 48-52)
into a reusable module, so per-prediction explanations can actually be used
-- from the API/dashboard, a CLI report, or anywhere else -- instead of only
existing as one-off notebook cells that nothing else in the project calls.

WHY THE RAW MODEL, NOT THE CALIBRATED ONE:
SHAP's TreeExplainer needs direct access to a tree ensemble's internal
structure to compute exact contributions efficiently. CalibratedClassifierCV
wraps the base estimator in a way that hides that structure, so SHAP can't
be run on it directly. This module therefore explains the RAW model's
reasoning (directionally correct and useful for "why"), while still
reporting the CALIBRATED probability as the headline number (the trustworthy
one -- see docs/09_model_results.md for why the raw model was overconfident
before calibration). These two numbers will not sum to exactly the same
value, and that's expected, not a bug -- SHAP explains the raw score's
reasoning, not a literal decomposition of the calibrated probability.

Run directly for a quick manual check:
    python src/features/explain.py
"""

import logging

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)


def build_explainer(raw_model):
    """One TreeExplainer can be reused across many predictions -- building it
    is the relatively expensive part, so callers (like the API) should build
    it once at startup, not per-request."""
    return shap.TreeExplainer(raw_model)


def explain_prediction(row, explainer, calibrated_model, feature_cols: list, top_n: int = 8) -> dict:
    """
    Explains a single prediction (one driver, one lap).

    row: a pandas Series or single-row DataFrame with all of feature_cols present.
    explainer: a shap.TreeExplainer built from the RAW (uncalibrated) model
               via build_explainer().
    calibrated_model: the calibrated model, used only for the headline
               probability shown to the user.
    feature_cols: exact feature list/order both models were trained on.
    top_n: how many top contributing features to return.

    Returns a dict with:
      - calibrated_win_probability: the trustworthy headline number (0-100)
      - base_rate: the model's average prediction across all drivers (0-100),
        i.e. what "no extra information" would predict
      - top_factors: list of {feature, actual_value, shap_impact_points,
        direction}, sorted by absolute impact, largest first
    """
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]

    missing = [c for c in feature_cols if c not in row.index]
    if missing:
        raise KeyError(f"Row is missing required feature columns: {missing}")

    X_row = pd.DataFrame([row[feature_cols]]).apply(pd.to_numeric, errors="coerce").fillna(-999)

    calibrated_prob = calibrated_model.predict_proba(X_row)[0][1]

    shap_values = explainer.shap_values(X_row)
    # shap_values shape is (rows, features, classes) for a multi-class-capable
    # TreeExplainer on a binary classifier -- select row 0, class index 1 ("won").
    if np.ndim(shap_values) == 3:
        row_shap = shap_values[0, :, 1]
        base_rate = explainer.expected_value[1]
    else:
        # Some shap versions return a single 2D array for binary classification.
        row_shap = shap_values[0]
        base_rate = explainer.expected_value

    explanation = pd.Series(row_shap, index=feature_cols).sort_values(key=np.abs, ascending=False)

    top_factors = []
    for feature, impact in explanation.head(top_n).items():
        top_factors.append({
            "feature": feature,
            "actual_value": round(float(row[feature]), 3) if pd.notna(row[feature]) else None,
            "shap_impact_points": round(float(impact) * 100, 2),
            "direction": "increases" if impact > 0 else "decreases",
        })

    return {
        "calibrated_win_probability": round(float(calibrated_prob) * 100, 2),
        "base_rate": round(float(base_rate) * 100, 2),
        "top_factors": top_factors,
    }


if __name__ == "__main__":
    import joblib

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)
    raw_model = joblib.load("models/win_probability_model_raw.pkl")
    calibrated_model = joblib.load("models/win_probability_model_calibrated.pkl")
    feature_cols = joblib.load("models/feature_columns.pkl")

    explainer = build_explainer(raw_model)

    sample_row = df.sample(1, random_state=1).iloc[0]
    result = explain_prediction(sample_row, explainer, calibrated_model, feature_cols)

    print(f"\nCalibrated win probability: {result['calibrated_win_probability']}%")
    print(f"Base rate (average across all drivers): {result['base_rate']}%")
    print("\nTop factors for this prediction:")
    for f in result["top_factors"]:
        print(f"  {f['feature']:30s} {f['direction']:10s} probability by "
              f"{abs(f['shap_impact_points']):.2f} points (actual value: {f['actual_value']})")