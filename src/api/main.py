"""
src/api/main.py

Thin FastAPI wrapper around the real win-probability model and StrategyEngine,
so the Next.js frontend (web/) can call the same intelligence directly.

Run from project root:
    uvicorn src.api.main:app --reload --port 8000

--------------------------------------------------------------------------
ERROR HANDLING NOTES (added as part of the "industrial-level" pass):

1. Startup file loading is wrapped so a missing data/model file (very likely
   right after a fresh clone, since data/ and models/*.pkl are gitignored --
   see docs/07_project_status.md) fails with ONE clear message telling the
   person exactly which pipeline command to run, instead of a raw traceback.
2. A global exception handler catches anything unexpected and returns a
   clean JSON error instead of leaking a Python stack trace to the client --
   the real error still gets logged server-side for debugging.
3. Query parameters (raceId, driverId, lap) are validated to be positive
   with FastAPI's Query(..., gt=0) rather than trusting arbitrary integers
   through to a pandas filter that would just silently return empty data.
4. CORS origins are read from an environment variable so this doesn't break
   the moment it's deployed somewhere other than localhost.
--------------------------------------------------------------------------
"""
import csv
import logging
import os
import sys

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.strategy.recommend_action import StrategyEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("racecraft.api")

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_PATH = os.environ.get("RACECRAFT_DATA_PATH", os.path.join(ROOT, "data", "processed", "cleaned_dataset.csv"))
MODEL_PATH = os.environ.get("RACECRAFT_MODEL_PATH", os.path.join(ROOT, "models", "win_probability_model_calibrated.pkl"))
RAW_MODEL_PATH = os.environ.get("RACECRAFT_RAW_MODEL_PATH", os.path.join(ROOT, "models", "win_probability_model_raw.pkl"))
FEATURES_PATH = os.environ.get("RACECRAFT_FEATURES_PATH", os.path.join(ROOT, "models", "feature_columns.pkl"))
RACES_CSV = os.environ.get("RACECRAFT_RACES_CSV", os.path.join(ROOT, "data", "raw", "ergast", "races.csv"))
DRIVERS_CSV = os.environ.get("RACECRAFT_DRIVERS_CSV", os.path.join(ROOT, "data", "raw", "ergast", "drivers.csv"))

app = FastAPI(title="RACECRAFT Strategy API")

_cors_origins = os.environ.get("RACECRAFT_CORS_ORIGINS", "http://localhost:3000,http://localhost:3100")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Anything that isn't an intentional HTTPException (a bad model input, a
    pandas edge case we didn't anticipate, etc.) lands here instead of
    returning a raw traceback to the client. The real error is still logged
    with full detail server-side -- this only changes what the CLIENT sees.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong processing that request. Please try again."},
    )


def _require_file(path: str, hint: str) -> str:
    if not os.path.exists(path):
        raise RuntimeError(
            f"Required file not found: {path}\n"
            f"This usually means the data pipeline hasn't been run yet "
            f"(data/ and models/*.pkl are intentionally not committed to "
            f"git -- see README.md). Fix: {hint}"
        )
    return path


try:
    df = pd.read_csv(_require_file(DATA_PATH, "run `python src/data/clean_data.py`"), low_memory=False)
    model = joblib.load(_require_file(MODEL_PATH, "run `python src/features/train_model.py`"))
    raw_model = joblib.load(_require_file(RAW_MODEL_PATH, "run `python src/features/train_model.py`"))
    feature_cols = joblib.load(_require_file(FEATURES_PATH, "run `python src/features/train_model.py`"))
except Exception:
    logger.exception("Startup failed while loading data/model files.")
    raise

real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
avg_pit_loss_ms = real_pit_durations.median() if len(real_pit_durations) > 0 else 22000
engine = StrategyEngine(model_path=MODEL_PATH, features_path=FEATURES_PATH, avg_pit_loss_ms=avg_pit_loss_ms)

try:
    with open(_require_file(RACES_CSV, "run `python src/data/fetch_ergast_data.py`"), encoding="utf-8") as f:
        RACE_NAMES = {r["raceId"]: r["name"] for r in csv.DictReader(f)}
    with open(_require_file(DRIVERS_CSV, "run `python src/data/fetch_ergast_data.py`"), encoding="utf-8") as f:
        DRIVER_NAMES = {d["driverId"]: f'{d["forename"]} {d["surname"]}' for d in csv.DictReader(f)}
except Exception:
    logger.exception("Startup failed while loading raw Ergast lookup CSVs.")
    raise

logger.info("RACECRAFT API ready: %d rows, %d features, %d races, %d drivers.",
            len(df), len(feature_cols), len(RACE_NAMES), len(DRIVER_NAMES))


def race_display_name(race_id) -> str:
    return RACE_NAMES.get(str(race_id), "")


def driver_display_name(driver_id) -> str:
    return DRIVER_NAMES.get(str(driver_id), "")


# Reusable, validated query parameter types -- every endpoint below shares
# these instead of a bare `int`, so a caller can't send raceId=-1 or lap=0
# and have it silently fall through to an empty-DataFrame 404 that's
# harder to distinguish from a genuinely unknown race/driver.
#
# These are FACTORY FUNCTIONS, not shared Query(...) instances: reusing the
# exact same Query() object as the default for two different parameters in
# one function (e.g. driverAId and driverBId both defaulting to the same
# object) confuses FastAPI's dependency resolution and produces a spurious
# 422 on every request -- caught by tests/test_api.py::test_compare_happy_path.
def RaceIdParam():
    return Query(..., gt=0, description="Ergast raceId, must be positive")


def DriverIdParam():
    return Query(..., gt=0, description="Ergast driverId, must be positive")


def LapParam():
    return Query(..., ge=1, description="Lap number, 1-indexed")


@app.get("/health")
def health():
    """Basic liveness/readiness check for deployment platforms (Render, Railway, etc.)."""
    return {"status": "ok", "rows_loaded": len(df), "races": len(RACE_NAMES)}


@app.get("/api/seasons")
def seasons():
    return sorted(df["year"].unique().tolist(), reverse=True)


@app.get("/api/races")
def races(year: int = Query(..., ge=1950, le=2100)):
    year_df = df[df["year"] == year][["raceId", "round", "circuit_name"]].drop_duplicates()
    if year_df.empty:
        raise HTTPException(404, f"no races found for year {year}")
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
def drivers(raceId: int = RaceIdParam()):
    race_df = df[df["raceId"] == raceId][["driverId", "driverRef", "code", "constructor_name"]].drop_duplicates()
    if race_df.empty:
        raise HTTPException(404, f"race {raceId} not found")
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
def race_info(raceId: int = RaceIdParam()):
    race_df = df[df["raceId"] == raceId]
    if race_df.empty:
        raise HTTPException(404, f"race {raceId} not found")
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
def laps(raceId: int = RaceIdParam(), driverId: int = DriverIdParam()):
    driver_race_df = df[(df["raceId"] == raceId) & (df["driverId"] == driverId)].sort_values("lap")
    if driver_race_df.empty:
        raise HTTPException(404, f"no lap data for driver {driverId} in race {raceId} "
                                  f"(check the raceId/driverId combination is valid)")
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


def _get_driver_lap_or_404(raceId: int, driverId: int, lap: int):
    """
    Shared lookup used by /api/strategy and /api/compare. Distinguishes two
    different failure reasons instead of one generic 404, since they need
    different fixes on the frontend: an unknown raceId/driverId pair vs. a
    real lap the driver didn't complete (retirement/DNF/collision).
    """
    driver_race_df = df[(df["raceId"] == raceId) & (df["driverId"] == driverId)].sort_values("lap")
    if driver_race_df.empty:
        raise HTTPException(404, f"no lap data for driver {driverId} in race {raceId} "
                                  f"(check the raceId/driverId combination is valid)")

    max_lap = int(driver_race_df["lap"].max())
    current_row_df = driver_race_df[driver_race_df["lap"] == lap]
    if current_row_df.empty:
        raise HTTPException(
            404,
            f"driver {driverId} has no data at lap {lap} in race {raceId} -- "
            f"this driver's data goes up to lap {max_lap} (likely retirement/DNF "
            f"or, if lap is beyond {max_lap}, simply past the race distance)",
        )
    return driver_race_df, current_row_df.iloc[0]


@app.get("/api/strategy")
def strategy(raceId: int = RaceIdParam(), driverId: int = DriverIdParam(), lap: int = LapParam()):
    driver_race_df, current_row = _get_driver_lap_or_404(raceId, driverId, lap)

    field_df = df[(df["raceId"] == raceId) & (df["lap"] == lap)]
    current = _row_to_strategy(current_row, field_df)

    # --- win probability trend up to this lap, real model.predict_proba per lap ---
    history_df = driver_race_df[driver_race_df["lap"] <= lap].copy()
    X_hist = history_df[feature_cols].fillna(-999)
    history_df["winProb"] = model.predict_proba(X_hist)[:, 1] * 100
    history = [{"lap": int(r.lap), "winProb": round(float(r.winProb), 2)} for r in history_df.itertuples()]

    # --- full field snapshot for this lap ---
    # Batched: 2 model calls total for the whole field, instead of 2 PER DRIVER
    # (previously a per-row loop calling recommend_full() -- see docs/09_model_results.md
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

    # --- real feature importance, top 10 (from the raw model -- CalibratedClassifierCV
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
            # Surfaced rather than silently used: a lap flagged as anomalous
            # (>600s, usually a red flag/safety car artifact -- see
            # docs/04_data_cleaning.md) still gets a prediction, but the
            # frontend can show a caveat instead of presenting it with full
            # confidence like any other lap.
            "anomalousLapTime": bool(current_row.get("anomalous_lap_time", 0) == 1),
        },
        "current": current,
        "history": history,
        "field": field,
        "featureImportance": feature_importance,
    }


@app.get("/api/compare")
def compare(
    raceId: int = RaceIdParam(),
    driverAId: int = DriverIdParam(),
    driverBId: int = DriverIdParam(),
    lap: int = LapParam(),
):
    if driverAId == driverBId:
        raise HTTPException(400, "driverAId and driverBId must be different drivers")

    result = {}
    for key, driver_id in (("driverA", driverAId), ("driverB", driverBId)):
        driver_race_df, current_row = _get_driver_lap_or_404(raceId, driver_id, lap)
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