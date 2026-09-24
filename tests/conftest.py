"""
tests/conftest.py

Builds a small, synthetic dataset + a tiny trained model in a temp directory,
so the test suite never touches the real ~93MB cleaned_dataset.csv or the
real model. This makes tests fast, and means CI (which won't have run the
full data pipeline) can still run them.

The synthetic data is deliberately small but realistic: 2 races, 5 drivers,
a handful of laps each, with the same column names and shapes of value the
real pipeline produces -- including a driver who retires early (a DNF) to
exercise that edge case, and one anomalous lap time to exercise that flag.
"""
import os
import numpy as np
import pandas as pd
import pytest
import joblib
from sklearn.ensemble import RandomForestClassifier


FEATURE_COLS = [
    "position", "grid", "gap_to_leader_ms", "gap_to_leader_s", "gap_per_lap_covered_s",
    "gap_to_ahead_ms", "cum_time_ms", "pit_stop_this_lap", "cumulative_pit_stops",
    "laps_since_last_pit", "tire_age_ratio", "drs_zone_proxy", "pace_delta_to_fastest_ms",
    "rolling_lap_time_ms", "position_change",
]


def _build_synthetic_dataset() -> pd.DataFrame:
    rows = []
    # Race 1: raceId=9001, 5 drivers, 10 laps, driver 104 retires after lap 6 (DNF)
    # Race 2: raceId=9002, 5 drivers, 8 laps, no DNFs
    races = [
        {"raceId": 9001, "year": 2099, "round": 1, "total_laps": 10, "circuit_name": "Test Circuit A"},
        {"raceId": 9002, "year": 2099, "round": 2, "total_laps": 8, "circuit_name": "Test Circuit B"},
    ]
    drivers = [
        {"driverId": 101, "driverRef": "alpha", "code": "ALP", "constructor_name": "Team Alpha"},
        {"driverId": 102, "driverRef": "bravo", "code": "BRA", "constructor_name": "Team Bravo"},
        {"driverId": 103, "driverRef": "charlie", "code": "CHA", "constructor_name": "Team Charlie"},
        {"driverId": 104, "driverRef": "delta", "code": "DEL", "constructor_name": "Team Delta"},
        {"driverId": 105, "driverRef": "echo", "code": "ECO", "constructor_name": "Team Echo"},
    ]

    for race in races:
        for pos, drv in enumerate(drivers, start=1):
            max_lap = race["total_laps"]
            if race["raceId"] == 9001 and drv["driverId"] == 104:
                max_lap = 6  # DNF after lap 6
            for lap in range(1, max_lap + 1):
                gap_ms = (pos - 1) * 1500 + lap * 20
                lap_ms = 90000 + np.random.randint(-500, 500)
                if race["raceId"] == 9001 and drv["driverId"] == 103 and lap == 5:
                    lap_ms = 650_000  # anomalous lap (>600s) -- red flag/safety car artifact
                pit_this_lap = 1 if (lap == max_lap // 2 and max_lap > 2) else 0
                rows.append({
                    "raceId": race["raceId"], "year": race["year"], "round": race["round"],
                    "circuit_name": race["circuit_name"], "total_laps": race["total_laps"],
                    "driverId": drv["driverId"], "driverRef": drv["driverRef"], "code": drv["code"],
                    "constructor_name": drv["constructor_name"],
                    "lap": lap, "position": pos, "grid": pos,
                    "gap_to_leader_ms": gap_ms, "gap_to_leader_s": gap_ms / 1000,
                    "gap_per_lap_covered_s": gap_ms / 1000 / max(lap, 1),
                    "gap_to_ahead_ms": 0.0 if pos == 1 else 800.0,
                    "cum_time_ms": lap_ms * lap,
                    "pit_stop_this_lap": pit_this_lap,
                    "cumulative_pit_stops": 1 if lap > max_lap // 2 else 0,
                    "laps_since_last_pit": lap if lap <= max_lap // 2 else lap - max_lap // 2,
                    "pit_duration_ms": 22000 if pit_this_lap else 0,
                    "tire_age_ratio": (lap if lap <= max_lap // 2 else lap - max_lap // 2) / race["total_laps"],
                    "drs_zone_proxy": 1 if pos != 1 else 0,
                    "pace_delta_to_fastest_ms": (pos - 1) * 100,
                    "rolling_lap_time_ms": lap_ms,
                    "position_change": 0,
                    "anomalous_lap_time": 1 if lap_ms > 600_000 else 0,
                    "won": 1 if (pos == 1 and lap == max_lap) else 0,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def synthetic_env(tmp_path_factory):
    """
    Writes a synthetic dataset + tiny trained model + minimal Ergast lookup
    CSVs to a temp directory, and returns the env vars needed to point
    src/api/main.py at them instead of the real data.
    """
    tmp_dir = tmp_path_factory.mktemp("racecraft_test_data")
    df = _build_synthetic_dataset()

    data_path = tmp_dir / "cleaned_dataset.csv"
    df.to_csv(data_path, index=False)

    X = df[FEATURE_COLS].fillna(-999)
    y = df["won"]
    model = RandomForestClassifier(n_estimators=10, max_depth=3, random_state=0)
    model.fit(X, y)

    model_path = tmp_dir / "model.pkl"
    raw_model_path = tmp_dir / "raw_model.pkl"
    features_path = tmp_dir / "features.pkl"
    joblib.dump(model, model_path)
    joblib.dump(model, raw_model_path)  # same model stands in for both in tests
    joblib.dump(FEATURE_COLS, features_path)

    races_csv = tmp_dir / "races.csv"
    drivers_csv = tmp_dir / "drivers.csv"
    pd.DataFrame([
        {"raceId": 9001, "name": "Test Grand Prix A"},
        {"raceId": 9002, "name": "Test Grand Prix B"},
    ]).to_csv(races_csv, index=False)
    pd.DataFrame([
        {"driverId": 101, "forename": "Alan", "surname": "Alpha"},
        {"driverId": 102, "forename": "Bea", "surname": "Bravo"},
        {"driverId": 103, "forename": "Cy", "surname": "Charlie"},
        {"driverId": 104, "forename": "Dee", "surname": "Delta"},
        {"driverId": 105, "forename": "Eli", "surname": "Echo"},
    ]).to_csv(drivers_csv, index=False)

    return {
        "RACECRAFT_DATA_PATH": str(data_path),
        "RACECRAFT_MODEL_PATH": str(model_path),
        "RACECRAFT_RAW_MODEL_PATH": str(raw_model_path),
        "RACECRAFT_FEATURES_PATH": str(features_path),
        "RACECRAFT_RACES_CSV": str(races_csv),
        "RACECRAFT_DRIVERS_CSV": str(drivers_csv),
    }


@pytest.fixture(scope="session")
def api_client(synthetic_env):
    """A TestClient wired to the synthetic dataset above, not the real data."""
    for key, value in synthetic_env.items():
        os.environ[key] = value

    from fastapi.testclient import TestClient
    from src.api import main as api_main
    # raise_server_exceptions=False: by default Starlette's TestClient re-raises
    # unhandled exceptions during tests (useful for debugging most of the time),
    # but that bypasses our custom @app.exception_handler(Exception) entirely.
    # We want tests to see exactly what a real client would see in production.
    return TestClient(api_main.app, raise_server_exceptions=False)