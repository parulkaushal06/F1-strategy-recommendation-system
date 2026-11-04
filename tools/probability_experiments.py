"""
tools/probability_experiments.py

Two evidence-gathering experiments, run BEFORE changing the production model,
so any change is justified by the numbers rather than assumed to help.

Experiment 1 - normalising win probabilities across the field
    Each driver's probability is predicted independently, so on a given lap the
    field's probabilities do not sum to 100%. Does rescaling them to sum to 100%
    (p / sum(p) per race+lap) improve Brier score / log loss on the test year?
    Uses the saved production model.

Experiment 2 - compare calibration windows
    The production model now calibrates on 2021-2023. Compare one, two, and
    three calibration years while holding the same base Random Forest fixed:
        A: last year only    (2023)
        B: last two years    (2022-2023)
        C: last three years  (2021-2023; production window)
    The shared base model trains only on years before 2021, so none of these
    candidate calibration rows overlap its training data.

Run from anywhere:
    python tools/probability_experiments.py
    python tools/probability_experiments.py --skip-calibration   # experiment 1 only
Outputs: reports/probability_experiments.csv (+ markdown tables on the console).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # train_model.py uses paths relative to the project root
sys.path.insert(0, str(ROOT))

from src.features.train_model import (  # noqa: E402
    CALIBRATION_YEAR,
    LABEL_COL,
    TEST_YEAR,
    load_cleaned_dataset,
    select_feature_columns,
)
from src.features.probability import normalize_field_probabilities  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

RESULTS_PATH = ROOT / "reports" / "probability_experiments.csv"
EPS = 1e-6
BUCKETS = [0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001]


def _scores(y, p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return {
        "roc_auc": roc_auc_score(y, p),
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, p, labels=[0, 1]),
    }


def _calibration_table(y, p):
    frame = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    frame["bucket"] = pd.cut(frame["p"], bins=BUCKETS, right=False)
    table = (frame.groupby("bucket", observed=True)
             .agg(rows=("y", "size"), mean_predicted=("p", "mean"), observed=("y", "mean"))
             .reset_index())
    table["bucket"] = table["bucket"].astype(str)
    # mean absolute calibration gap, weighted by rows (a simple ECE)
    ece = float((table["rows"] * (table["mean_predicted"] - table["observed"]).abs()).sum() / table["rows"].sum())
    return table, ece


def _print_scores(title, rows):
    print(f"\n### {title}\n")
    print("| Variant | ROC-AUC | Brier | Log loss | Calibration gap (ECE) |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['variant']} | {r['roc_auc']:.4f} | {r['brier']:.4f} | {r['log_loss']:.4f} | {r['ece']:.4f} |")


def _print_buckets(title, tables):
    print(f"\n### {title}\n")
    names = list(tables)
    print("| Predicted bucket | Rows | " + " | ".join(f"{n}: predicted / observed" for n in names) + " |")
    print("|---|---|" + "---|" * len(names))
    base = tables[names[0]]
    for i, row in base.iterrows():
        cells = []
        for n in names:
            t = tables[n]
            match = t[t["bucket"] == row["bucket"]]
            cells.append(f"{match.iloc[0]['mean_predicted']:.3f} / {match.iloc[0]['observed']:.3f}" if len(match) else "-")
        print(f"| {row['bucket']} | {int(row['rows']):,} | " + " | ".join(cells) + " |")


def experiment_normalisation(test, feature_cols, model_path):
    if not model_path.exists():
        logger.warning("Production model not found at %s; skipping experiment 1.", model_path)
        return []
    model = joblib.load(model_path)
    test = test.copy()
    test["p_raw"] = model.predict_proba(test[feature_cols].fillna(-999))[:, 1]
    test["p_norm"] = test.groupby(["raceId", "lap"])["p_raw"].transform(
        lambda probabilities: normalize_field_probabilities(probabilities.to_numpy())
    )

    sums = test.groupby(["raceId", "lap"])["p_raw"].sum()
    print("\n### Experiment 1: field probability sum per lap (before normalising)\n")
    print(f"mean {sums.mean():.3f}, median {sums.median():.3f}, min {sums.min():.3f}, max {sums.max():.3f} "
          f"(100% would be 1.000), over {len(sums):,} race-laps")

    y = test[LABEL_COL]
    rows, tables = [], {}
    for name, col in (("Raw (production)", "p_raw"), ("Normalised to 100%", "p_norm")):
        table, ece = _calibration_table(y, test[col])
        tables[name] = table
        rows.append({"experiment": "normalisation", "variant": name, **_scores(y, test[col]), "ece": ece})
    _print_scores(f"Experiment 1: normalising across the field (test year {TEST_YEAR})", rows)
    _print_buckets("Experiment 1: calibration buckets, predicted / observed", tables)
    return rows


def experiment_calibration_windows(df, feature_cols, test, trees):
    calib_end = CALIBRATION_YEAR  # last calibration year (2023)
    available = sorted(df["year"].unique())
    windows = {"A: last year": [calib_end], "B: last 2 years": [calib_end - 1, calib_end],
               "C: last 3 years": [calib_end - 2, calib_end - 1, calib_end]}
    base_end = calib_end - 2  # base model trains on years < this, so every window stays held out
    for name, years in windows.items():
        missing = [y for y in years if y not in available]
        if missing:
            logger.warning("Years %s missing from the dataset; skipping window %s.", missing, name)
    windows = {n: ys for n, ys in windows.items() if all(y in available for y in ys)}

    train = df[df["year"] < base_end]
    if train.empty or not windows:
        logger.warning("Not enough data for experiment 2; skipping.")
        return []
    logger.info("Experiment 2: training base Random Forest on %d rows (years < %d)...", len(train), base_end)
    base = RandomForestClassifier(n_estimators=trees, max_depth=12, min_samples_leaf=5,
                                  class_weight="balanced", random_state=42, n_jobs=-1)
    base.fit(train[feature_cols].fillna(-999), train[LABEL_COL])

    y = test[LABEL_COL]
    x_test = test[feature_cols].fillna(-999)
    rows, tables = [], {}
    for name, years in windows.items():
        calib = df[df["year"].isin(years)]
        model = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
        model.fit(calib[feature_cols].fillna(-999), calib[LABEL_COL])
        p = model.predict_proba(x_test)[:, 1]
        table, ece = _calibration_table(y, p)
        tables[name] = table
        rows.append({"experiment": "calibration_window", "variant": f"{name} ({years[0]}-{years[-1]})",
                     **_scores(y, p), "ece": ece})
    _print_scores(f"Experiment 2: calibration window (same base model trained on years < {base_end}, test {TEST_YEAR})", rows)
    _print_buckets("Experiment 2: calibration buckets, predicted / observed", tables)
    return rows


def run(model_path, skip_calibration, trees):
    df = load_cleaned_dataset()
    feature_cols = select_feature_columns(df)
    test = df[df["year"] == TEST_YEAR]
    if test.empty:
        raise ValueError(f"No rows for TEST_YEAR={TEST_YEAR}.")

    results = experiment_normalisation(test, feature_cols, model_path)
    if not skip_calibration:
        results += experiment_calibration_windows(df, feature_cols, test, trees)

    if results:
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(results).to_csv(RESULTS_PATH, index=False)
        logger.info("Saved %s", RESULTS_PATH)
    print("\nLower Brier / log loss / ECE is better. The production calibration window is the three-year variant.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "win_probability_model_calibrated.pkl")
    parser.add_argument("--skip-calibration", action="store_true", help="run experiment 1 only (fast)")
    parser.add_argument("--trees", type=int, default=200, help="trees for experiment 2's base model")
    args = parser.parse_args()
    try:
        run(args.model, args.skip_calibration, args.trees)
    except Exception:
        logger.exception("probability_experiments.py failed.")
        sys.exit(1)
