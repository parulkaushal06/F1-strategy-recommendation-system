"""
src/features/train_model.py

Script version of notebooks/04_modeling.ipynb — trains the win-probability
RandomForestClassifier on data/processed/cleaned_dataset.csv and saves the
model + feature column list to models/.

Run from project root, after clean_data.py:
    python src/features/train_model.py
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (roc_auc_score, precision_score, recall_score,
                              f1_score, classification_report)
import joblib
import os

PROCESSED_PATH = "data/processed/cleaned_dataset.csv"
MODELS_DIR = "models"


def train():
    df = pd.read_csv(PROCESSED_PATH, low_memory=False)
    print("Loaded cleaned dataset -> shape:", df.shape)

    # Exclude leakage columns, identifiers, and unencoded text columns
    leakage_cols = ["points", "positionOrder", "statusId"]
    identifier_cols = ["raceId", "driverId", "driver_number", "session_key", "meeting_key"]
    text_cols = df.select_dtypes(include=["object"]).columns.tolist()
    label_col = "won"

    exclude = set(leakage_cols + identifier_cols + text_cols + [label_col])
    feature_cols = [c for c in df.columns if c not in exclude and df[c].dtype != "object"]
    print(f"\n{len(feature_cols)} features selected:")
    print(feature_cols)

    X = df[feature_cols].copy()
    y = df[label_col].copy()
    X = X.fillna(-999)

    # Time-based split by race year, not random -- no race in both sets
    TEST_YEAR = df["year"].max()
    train_mask = df["year"] < TEST_YEAR
    test_mask = df["year"] == TEST_YEAR

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    print(f"\nTrain: {X_train.shape[0]} rows ({y_train.mean()*100:.2f}% won)")
    print(f"Test:  {X_test.shape[0]} rows ({y_test.mean()*100:.2f}% won)")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    print("\nModel trained.")

    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_pred_proba)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"\nROC-AUC:   {auc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 score:  {f1:.4f}")
    print()
    print(classification_report(y_test, y_pred, target_names=["Not won", "Won"]))

    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop 15 feature importances:")
    print(importances.head(15))

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODELS_DIR, "win_probability_model.pkl"))
    joblib.dump(feature_cols, os.path.join(MODELS_DIR, "feature_columns.pkl"))
    print(f"\nSaved -> {MODELS_DIR}/win_probability_model.pkl")
    print(f"Saved -> {MODELS_DIR}/feature_columns.pkl")

    return model, feature_cols, {"roc_auc": auc, "precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    train()