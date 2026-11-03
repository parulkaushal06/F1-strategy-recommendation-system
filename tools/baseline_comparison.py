"""
tools/baseline_comparison.py

Compares the production win-probability model against simple baselines on the
SAME held-out test year, so the headline ROC-AUC has context. Late in a race
the leader usually wins anyway, so a high AUC alone proves little -- what
matters is how much the model adds over trivial rules.

Uses the exact split from src/features/train_model.py:
    train = years before CALIBRATION_YEAR, test = TEST_YEAR.
Baselines are fit on the training years only (never on the test year).

Baselines
  1. Constant        : every row gets the training-set win rate
  2. Grid only       : logistic regression on starting grid position
  3. Position only   : logistic regression on current running position
  4. Position + race progress : logistic regression on position, race_progress
                       and their interaction (position matters more late)
  5. "Leader wins"   : rank rows by -position (AUC, precision/recall only;
                       it outputs a rank, not a probability, so no Brier)
Production model: models/win_probability_model_calibrated.pkl

Also prints: AUC by race-progress bucket (is the model useful EARLY, when it
is hard?) and a calibration table for the production model.

Run from anywhere:
    python tools/baseline_comparison.py
Outputs:
    reports/baseline_comparison.csv  (+ markdown tables printed to the console)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # train_model.py uses paths relative to the project root
sys.path.insert(0, str(ROOT))

from src.features.train_model import (  # noqa: E402
    CALIBRATION_YEAR,
    LABEL_COL,
    TEST_YEAR,
    load_cleaned_dataset,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

RESULTS_PATH = ROOT / "reports" / "baseline_comparison.csv"
PROGRESS_BUCKETS = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]


def _safe_auc(y, score):
    return roc_auc_score(y, score) if y.nunique() > 1 else float("nan")


def _fit_logreg(train_df, test_df, columns):
    """Logistic regression on `columns`; missing values -> train median."""
    medians = train_df[columns].median()
    x_train = train_df[columns].fillna(medians)
    x_test = test_df[columns].fillna(medians)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    model.fit(x_train, train_df[LABEL_COL])
    return model.predict_proba(x_test)[:, 1]


def _with_interaction(df):
    out = df.copy()
    out["position_x_progress"] = out["position"] * out["race_progress"]
    return out


def _row(name, y, proba=None, score=None, preds=None):
    """One results row. `proba` = probabilities, `score` = rank-only score."""
    s = proba if proba is not None else score
    row = {"model": name, "roc_auc": _safe_auc(y, s) if s is not None else float("nan")}
    row["brier"] = brier_score_loss(y, proba) if proba is not None else float("nan")
    if preds is None and proba is not None:
        preds = (proba >= 0.5).astype(int)
    if preds is not None:
        row["precision"] = precision_score(y, preds, zero_division=0)
        row["recall"] = recall_score(y, preds, zero_division=0)
    else:
        row["precision"] = row["recall"] = float("nan")
    return row


def _fmt(value, digits=4):
    return "n/a" if pd.isna(value) else f"{value:.{digits}f}"


def run(model_path: Path, features_path: Path) -> pd.DataFrame:
    df = load_cleaned_dataset()
    for col in ("position", "grid", "race_progress"):
        if col not in df.columns:
            raise KeyError(f"Column '{col}' missing from the dataset; cannot build baselines.")

    train = df[df["year"] < CALIBRATION_YEAR]
    test = df[df["year"] == TEST_YEAR].copy()
    if train.empty or test.empty:
        raise ValueError(f"Empty split (train={len(train)}, test={len(test)}); check the year settings.")
    y = test[LABEL_COL]
    base_rate = float(train[LABEL_COL].mean())
    logger.info("train rows=%d, test rows=%d, train win rate=%.4f, test win rate=%.4f",
                len(train), len(test), base_rate, y.mean())

    results = []

    # 1. constant
    const = np.full(len(test), base_rate)
    results.append(_row("Constant (training win rate)", y, proba=const, preds=np.zeros(len(test), dtype=int)))

    # 2-4. logistic baselines
    results.append(_row("Grid position only", y, proba=_fit_logreg(train, test, ["grid"])))
    test["p_position"] = _fit_logreg(train, test, ["position"])
    results.append(_row("Current position only", y, proba=test["p_position"].to_numpy()))
    train_i, test_i = _with_interaction(train), _with_interaction(test)
    test["p_pos_prog"] = _fit_logreg(train_i, test_i, ["position", "race_progress", "position_x_progress"])
    results.append(_row("Position + race progress", y, proba=test["p_pos_prog"].to_numpy()))

    # 5. leader-wins rule (rank only)
    results.append(_row('"Current leader wins" rule', y, score=-test["position"].to_numpy(),
                        preds=(test["position"] == 1).astype(int).to_numpy()))

    # production model
    rf_proba = None
    if model_path.exists() and features_path.exists():
        model = joblib.load(model_path)
        feature_cols = joblib.load(features_path)
        rf_proba = model.predict_proba(test[feature_cols].fillna(-999))[:, 1]
        test["p_model"] = rf_proba
        results.append(_row("Random Forest (calibrated, production)", y, proba=rf_proba))
    else:
        logger.warning("Production model or feature list not found (%s) -- skipping it.", model_path)

    results_df = pd.DataFrame(results)

    # --- AUC by race progress ---------------------------------------------
    progress_rows = []
    for low, high in PROGRESS_BUCKETS:
        sub = test[(test["race_progress"] >= low) & (test["race_progress"] < high)]
        entry = {"race_progress": f"{int(low * 100)}-{min(int(high * 100), 100)}%", "rows": len(sub),
                 "position_only_auc": _safe_auc(sub[LABEL_COL], sub["p_position"]) if len(sub) else float("nan"),
                 "position_progress_auc": _safe_auc(sub[LABEL_COL], sub["p_pos_prog"]) if len(sub) else float("nan")}
        if rf_proba is not None and len(sub):
            entry["model_auc"] = _safe_auc(sub[LABEL_COL], sub["p_model"])
        progress_rows.append(entry)
    progress_df = pd.DataFrame(progress_rows)

    # --- calibration table for the production model ------------------------
    calib_df = None
    if rf_proba is not None:
        bins = [0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001]
        test["bucket"] = pd.cut(test["p_model"], bins=bins, right=False)
        calib_df = (test.groupby("bucket", observed=True)
                    .agg(rows=(LABEL_COL, "size"), mean_predicted=("p_model", "mean"),
                         observed_win_rate=(LABEL_COL, "mean"))
                    .reset_index())
        calib_df["bucket"] = calib_df["bucket"].astype(str)

    # --- output --------------------------------------------------------------
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(RESULTS_PATH, index=False)
    logger.info("Saved %s", RESULTS_PATH)

    print(f"\n### Baselines vs model (test year {TEST_YEAR}, trained on years < {CALIBRATION_YEAR})\n")
    print("| Model | ROC-AUC | Brier | Precision | Recall |")
    print("|---|---|---|---|---|")
    for r in results_df.itertuples():
        print(f"| {r.model} | {_fmt(r.roc_auc)} | {_fmt(r.brier)} | {_fmt(r.precision, 3)} | {_fmt(r.recall, 3)} |")

    print(f"\n### ROC-AUC by race progress (test year {TEST_YEAR})\n")
    has_model = "model_auc" in progress_df.columns
    print("| Race progress | Rows | Position only | Position + progress |" + (" Random Forest |" if has_model else ""))
    print("|---|---|---|---|" + ("---|" if has_model else ""))
    for r in progress_df.to_dict("records"):
        line = f"| {r['race_progress']} | {r['rows']:,} | {_fmt(r['position_only_auc'])} | {_fmt(r['position_progress_auc'])} |"
        if has_model:
            line += f" {_fmt(r.get('model_auc'))} |"
        print(line)

    if calib_df is not None:
        print("\n### Calibration of the production model\n")
        print("| Predicted probability bucket | Rows | Mean predicted | Observed win rate |")
        print("|---|---|---|---|")
        for r in calib_df.itertuples():
            print(f"| {r.bucket} | {r.rows:,} | {r.mean_predicted:.3f} | {r.observed_win_rate:.3f} |")
    print()
    return results_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "win_probability_model_calibrated.pkl")
    parser.add_argument("--features", type=Path, default=ROOT / "models" / "feature_columns.pkl")
    args = parser.parse_args()
    try:
        run(args.model, args.features)
    except Exception:
        logger.exception("baseline_comparison.py failed.")
        sys.exit(1)