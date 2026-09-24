"""
tests/test_api.py

Tests the FastAPI layer (src/api/main.py) against a small synthetic dataset
(see conftest.py) -- not the real ~93MB dataset, so these run fast and don't
require the full pipeline to have been executed first.

Covers the error-handling work specifically: invalid input, unknown
race/driver, DNF laps, and the anomalous-lap-time flag.
"""


def test_health_check(api_client):
    res = api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_seasons_returns_synthetic_year(api_client):
    res = api_client.get("/api/seasons")
    assert res.status_code == 200
    assert 2099 in res.json()


def test_races_for_valid_year(api_client):
    res = api_client.get("/api/races", params={"year": 2099})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert body[0]["name"] == "Test Grand Prix A"


def test_races_for_unknown_year_returns_404_not_500(api_client):
    # 1960 passes FastAPI's own ge=1950 validation, so this actually
    # exercises our endpoint's own "no races found" 404, not the separate
    # 422 that an out-of-range year (e.g. 1800) would trigger instead.
    res = api_client.get("/api/races", params={"year": 1960})
    assert res.status_code == 404


def test_races_rejects_year_out_of_range(api_client):
    # year=1 should fail FastAPI's own ge=1950 validation before hitting our code at all
    res = api_client.get("/api/races", params={"year": 1})
    assert res.status_code == 422


def test_strategy_happy_path(api_client):
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 101, "lap": 3})
    assert res.status_code == 200
    body = res.json()
    assert 0 <= body["current"]["winProbability"] <= 100
    assert body["meta"]["position"] == 1
    assert len(body["field"]) == 5  # all 5 drivers still racing at lap 3


def test_strategy_rejects_non_positive_ids(api_client):
    res = api_client.get("/api/strategy", params={"raceId": -1, "driverId": 101, "lap": 3})
    assert res.status_code == 422  # caught by Query(gt=0), never reaches pandas


def test_strategy_rejects_lap_zero(api_client):
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 101, "lap": 0})
    assert res.status_code == 422  # caught by Query(ge=1)


def test_strategy_unknown_race_returns_clean_404(api_client):
    res = api_client.get("/api/strategy", params={"raceId": 99999, "driverId": 101, "lap": 3})
    assert res.status_code == 404
    assert "99999" in res.json()["detail"]


def test_strategy_dnf_driver_past_their_last_lap_gives_helpful_message(api_client):
    """
    Driver 104 in race 9001 retires after lap 6 (see conftest's synthetic
    data). Asking for lap 8 should fail clearly, and the error message
    should mention where their data actually ends -- this is the DNF edge
    case that used to just be a generic 404 with no context.
    """
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 104, "lap": 8})
    assert res.status_code == 404
    assert "6" in res.json()["detail"]  # mentions the real last lap


def test_strategy_surfaces_anomalous_lap_flag(api_client):
    """Driver 103's lap 5 in race 9001 is a synthetic red-flag/safety-car artifact."""
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 103, "lap": 5})
    assert res.status_code == 200
    assert res.json()["meta"]["anomalousLapTime"] is True


def test_strategy_normal_lap_not_flagged_anomalous(api_client):
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 103, "lap": 3})
    assert res.status_code == 200
    assert res.json()["meta"]["anomalousLapTime"] is False


def test_compare_happy_path(api_client):
    res = api_client.get("/api/compare", params={"raceId": 9001, "driverAId": 101, "driverBId": 102, "lap": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["driverA"]["driverId"] == 101
    assert body["driverB"]["driverId"] == 102


def test_compare_rejects_comparing_driver_to_self(api_client):
    res = api_client.get("/api/compare", params={"raceId": 9001, "driverAId": 101, "driverBId": 101, "lap": 3})
    assert res.status_code == 400


def test_unhandled_error_does_not_leak_stack_trace(api_client, monkeypatch):
    """
    Force an unexpected exception inside a route and confirm the client gets
    a clean generic message, not a raw traceback -- this is what the global
    exception_handler in main.py exists for.
    """
    from src.api import main as api_main

    def boom(*args, **kwargs):
        raise ValueError("simulated unexpected failure")

    monkeypatch.setattr(api_main, "_row_to_strategy", boom)
    res = api_client.get("/api/strategy", params={"raceId": 9001, "driverId": 101, "lap": 3})
    assert res.status_code == 500
    assert "Traceback" not in res.text
    assert "simulated unexpected failure" not in res.text
    assert res.json()["detail"] == "Something went wrong processing that request. Please try again."