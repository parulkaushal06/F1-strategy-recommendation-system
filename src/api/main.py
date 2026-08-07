"""
src/api/main.py

Thin FastAPI wrapper around the real win-probability model and StrategyEngine,
so the Next.js frontend (web/) can call the same intelligence the Streamlit
dashboard (dashboard/app.py) uses, instead of the placeholder numbers the
first pass of the UI shipped with.

Run from project root:
    uvicorn src.api.main:app --reload --port 8000
"""
import os
import sys
import csv

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.strategy.recommend_action import StrategyEngine

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "cleaned_dataset.csv")
MODEL_PATH = os.path.join(ROOT, "models", "win_probability_model_calibrated.pkl")
RAW_MODEL_PATH = os.path.join(ROOT, "models", "win_probability_model_raw.pkl")
FEATURES_PATH = os.path.join(ROOT, "models", "feature_columns.pkl")
RACES_CSV = os.path.join(ROOT, "data", "raw", "ergast", "races.csv")
DRIVERS_CSV = os.path.join(ROOT, "data", "raw", "ergast", "drivers.csv")

app = FastAPI(title="RACECRAFT Strategy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# --- load once at startup, same pattern as the Streamlit dashboard's caching ---
df = pd.read_csv(DATA_PATH, low_memory=False)
model = joblib.load(MODEL_PATH)  # calibrated — used for every probability prediction
raw_model = joblib.load(RAW_MODEL_PATH)  # underlying tree model — feature_importances_ only
feature_cols = joblib.load(FEATURES_PATH)

real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
avg_pit_loss_ms = real_pit_durations.median() if len(real_pit_durations) > 0 else 22000
engine = StrategyEngine(model_path=MODEL_PATH, features_path=FEATURES_PATH, avg_pit_loss_ms=avg_pit_loss_ms)

with open(RACES_CSV, encoding="utf-8") as f:
    RACE_NAMES = {r["raceId"]: r["name"] for r in csv.DictReader(f)}
with open(DRIVERS_CSV, encoding="utf-8") as f:
    DRIVER_NAMES = {d["driverId"]: f'{d["forename"]} {d["surname"]}' for d in csv.DictReader(f)}


def race_display_name(race_id) -> str:
    return RACE_NAMES.get(str(race_id), "")


def driver_display_name(driver_id) -> str:
    return DRIVER_NAMES.get(str(driver_id), "")


@app.get("/api/seasons")
def seasons():
    return sorted(df["year"].unique().tolist(), reverse=True)


@app.get("/api/races")
def races(year: int):
    year_df = df[df["year"] == year][["raceId", "round", "circuit_name"]].drop_duplicates()
    year_df = year_df.sort_values("round")
    return [
        {
            "raceId": int(row.raceId),
            "round": int(row.round),
            "name": race_display_name(row.raceId) or row.circuit_name,
            "circuitName": row.circuit_name,
        }
        for row in year_df.itertuples()
    ]


@app.get("/api/drivers")
def drivers(raceId: int):
    race_df = df[df["raceId"] == raceId][["driverId", "driverRef", "code", "constructor_name"]].drop_duplicates()
    if race_df.empty:
        raise HTTPException(404, "race not found")
    return [
        {
            "driverId": int(row.driverId),
            "code": row.code,
            "name": driver_display_name(row.driverId) or row.driverRef,
            "team": row.constructor_name,
        }
        for row in race_df.sort_values("code").itertuples()
    ]


@app.get("/api/race-info")
def race_info(raceId: int):
    race_df = df[df["raceId"] == raceId]
    if race_df.empty:
        raise HTTPException(404, "race not found")
    row = race_df.iloc[0]
    return {
        "raceId": raceId,
        "year": int(row["year"]),
        "round": int(row["round"]),
        "name": race_display_name(raceId) or row["circuit_name"],
        "circuitName": row["circuit_name"],
        "totalLaps": int(row["total_laps"]),
    }


@app.get("/api/laps")
def laps(raceId: int, driverId: int):
    driver_race_df = df[(df["raceId"] == raceId) & (df["driverId"] == driverId)].sort_values("lap")
    if driver_race_df.empty:
        raise HTTPException(404, "no lap data for this driver in this race")
    return {
        "maxLap": int(driver_race_df["lap"].max()),
        "totalLaps": int(driver_race_df["total_laps"].iloc[0]),
    }


def _row_to_strategy(row, field_df):
    result = engine.recommend_full(row, same_lap_field_df=field_df)
    return {
        "winProbability": result["current_win_probability"],
        "pitUrgencyScore": result["pit_urgency_score"],
        "tireAgeRatio": result["tire_age_ratio"],
        "lapsOnCurrentTires": result["laps_on_current_tires"],
        "pitRecommendation": result["pit_recommendation"],
        "drsRecommendation": result["drs_recommendation"],
        "ersRecommendation": result["ers_recommendation"],
        "raceCraftRecommendation": result["race_craft_recommendation"],
        "gapToAheadMs": result["gap_to_ahead_ms"],
        "gapToBehindMs": result["gap_to_behind_ms"],
        "simulatedPitNow": {
            "winProbability": result["model_context_if_pit_now"]["simulated_win_probability"],
            "probabilityChange": result["model_context_if_pit_now"]["probability_change"],
            "note": result["model_context_if_pit_now"]["note"],
        },
    }


@app.get("/api/strategy")
def strategy(raceId: int, driverId: int, lap: int):
    driver_race_df = df[(df["raceId"] == raceId) & (df["driverId"] == driverId)].sort_values("lap")
    if driver_race_df.empty:
        raise HTTPException(404, "no lap data for this driver in this race")

    current_row_df = driver_race_df[driver_race_df["lap"] == lap]
    if current_row_df.empty:
        raise HTTPException(404, "no data for this exact lap (possible retirement/DNF)")
    current_row = current_row_df.iloc[0]

    field_df = df[(df["raceId"] == raceId) & (df["lap"] == lap)]
    current = _row_to_strategy(current_row, field_df)

    # --- win probability trend up to this lap, real model.predict_proba per lap ---
    history_df = driver_race_df[driver_race_df["lap"] <= lap].copy()
    X_hist = history_df[feature_cols].fillna(-999)
    history_df["winProb"] = model.predict_proba(X_hist)[:, 1] * 100
    history = [{"lap": int(r.lap), "winProb": round(float(r.winProb), 2)} for r in history_df.itertuples()]

    # --- full field snapshot for this lap ---
    # Batched: 2 model calls total for the whole field, instead of 2 PER DRIVER
    # (previously a per-row loop calling recommend_full() — see docs/09_model_results.md
    # for the ~5x speed impact this had on page load time).
    field_sorted = field_df.sort_values("position").reset_index(drop=True)
    batch_results = engine.recommend_batch(field_sorted, same_lap_field_df=field_df)

    field = []
    for row_dict, r in zip(field_sorted.to_dict("records"), batch_results):
        field.append({
            "position": int(row_dict["position"]),
            "driverId": int(row_dict["driverId"]),
            "code": row_dict["code"],
            "team": row_dict["constructor_name"],
            "winProbability": r["current_win_probability"],
            "pitRecommendation": r["pit_recommendation"].split(" (")[0],
            "drsAvailable": "AVAILABLE" in r["drs_recommendation"],
            "raceCraftRecommendation": r["race_craft_recommendation"].split(" (")[0],
        })

    # --- real feature importance, top 10 (from the raw model — CalibratedClassifierCV
    # wraps the base estimator in CV folds and doesn't expose feature_importances_ directly) ---
    importances = pd.Series(raw_model.feature_importances_, index=feature_cols).sort_values(ascending=False).head(10)
    feature_importance = [{"feature": k, "importance": round(float(v), 4)} for k, v in importances.items()]

    return {
        "meta": {
            "circuitName": current_row["circuit_name"],
            "year": int(current_row["year"]),
            "round": int(current_row["round"]),
            "totalLaps": int(current_row["total_laps"]),
            "maxLap": int(driver_race_df["lap"].max()),
            "position": int(current_row["position"]),
            "team": current_row["constructor_name"],
            "code": current_row["code"],
        },
        "current": current,
        "history": history,
        "field": field,
        "featureImportance": feature_importance,
    }


@app.get("/api/compare")
def compare(raceId: int, driverAId: int, driverBId: int, lap: int):
    result = {}
    for key, driver_id in (("driverA", driverAId), ("driverB", driverBId)):
        driver_race_df = df[(df["raceId"] == raceId) & (df["driverId"] == driver_id)].sort_values("lap")
        if driver_race_df.empty:
            raise HTTPException(404, f"no lap data for driver {driver_id} in this race")
        current_row_df = driver_race_df[driver_race_df["lap"] == lap]
        if current_row_df.empty:
            raise HTTPException(404, f"no data for driver {driver_id} at lap {lap}")
        current_row = current_row_df.iloc[0]
        field_df = df[(df["raceId"] == raceId) & (df["lap"] == lap)]
        current = _row_to_strategy(current_row, field_df)

        history_df = driver_race_df[driver_race_df["lap"] <= lap].copy()
        X_hist = history_df[feature_cols].fillna(-999)
        history_df["winProb"] = model.predict_proba(X_hist)[:, 1] * 100
        history = [{"lap": int(r.lap), "winProb": round(float(r.winProb), 2)} for r in history_df.itertuples()]

        result[key] = {
            "driverId": driver_id,
            "code": current_row["code"],
            "name": driver_display_name(driver_id),
            "team": current_row["constructor_name"],
            "position": int(current_row["position"]),
            "lapsOnCurrentTires": current["lapsOnCurrentTires"],
            "current": current,
            "history": history,
        }
    return result