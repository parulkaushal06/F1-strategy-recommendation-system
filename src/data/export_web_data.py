"""
One-off export of real historical data (already in data/raw/ergast/) into small
JSON snapshots the Next.js frontend (web/) reads at build/request time. Not part
of the ML pipeline - this only feeds the marketing/dashboard UI with real numbers
instead of placeholders.
"""
import csv
import json
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "ergast"
OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def load_csv(name):
    with open(RAW / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


races = load_csv("races.csv")
circuits = {c["circuitId"]: c for c in load_csv("circuits.csv")}
drivers = {d["driverId"]: d for d in load_csv("drivers.csv")}
constructors = {c["constructorId"]: c for c in load_csv("constructors.csv")}
results = load_csv("results.csv")
driver_standings = load_csv("driver_standings.csv")
constructor_standings = load_csv("constructor_standings.csv")
pit_stops = load_csv("pit_stops.csv")

season_2023 = sorted(
    (r for r in races if r["year"] == "2023"), key=lambda r: int(r["round"])
)
belgian_gp = next(r for r in season_2023 if r["name"] == "Belgian Grand Prix")
hungarian_gp = next(r for r in season_2023 if r["name"] == "Hungarian Grand Prix")
belgian_id, hungarian_id = belgian_gp["raceId"], hungarian_gp["raceId"]

# --- season calendar -------------------------------------------------------
CURRENT_ROUND = int(belgian_gp["round"])
season_out = []
for r in season_2023:
    c = circuits.get(r["circuitId"], {})
    rnd = int(r["round"])
    status = "done" if rnd < CURRENT_ROUND else ("next" if rnd == CURRENT_ROUND else "upcoming")
    season_out.append(
        {
            "raceId": int(r["raceId"]),
            "round": rnd,
            "name": r["name"],
            "location": c.get("location"),
            "country": c.get("country"),
            "date": r["date"],
            "status": status,
        }
    )
(OUT / "season_2023.json").write_text(json.dumps(season_out, indent=2))

# --- standings after round 11 (Hungary), before Belgium --------------------
def top5(standings, id_field, name_lookup, race_id):
    rows = [s for s in standings if s["raceId"] == race_id]
    rows.sort(key=lambda s: int(s["position"]))
    out = []
    for s in rows[:5]:
        entity = name_lookup[s[id_field]]
        name = (
            f'{entity["forename"]} {entity["surname"]}'
            if "forename" in entity
            else entity["name"]
        )
        out.append({"name": name, "points": int(s["points"]), "position": int(s["position"])})
    return out


standings_out = {
    "after_round": int(hungarian_gp["round"]),
    "drivers": top5(driver_standings, "driverId", drivers, hungarian_id),
    "constructors": top5(constructor_standings, "constructorId", constructors, hungarian_id),
}
(OUT / "standings_2023_r11.json").write_text(json.dumps(standings_out, indent=2))

# --- Belgian GP real results + pit counts + fastest lap --------------------
race_results = [r for r in results if r["raceId"] == belgian_id]
race_results.sort(key=lambda r: int(r["positionOrder"]))
pit_counts = {}
for p in pit_stops:
    if p["raceId"] == belgian_id:
        pit_counts[p["driverId"]] = pit_counts.get(p["driverId"], 0) + 1

results_out = []
for r in race_results[:10]:
    d = drivers[r["driverId"]]
    c = constructors[r["constructorId"]]
    results_out.append(
        {
            "position": int(r["positionOrder"]),
            "code": d["code"],
            "name": f'{d["forename"]} {d["surname"]}',
            "team": c["name"],
            "time": r["time"] if r["time"] != r"\N" else None,
            "pitStops": pit_counts.get(r["driverId"], 0),
            "fastestLap": r.get("rank") == "1",
        }
    )
(OUT / "belgian_gp_2023_results.json").write_text(json.dumps(results_out, indent=2))

print(f"Wrote season_2023.json ({len(season_out)} races)")
print(f"Wrote standings_2023_r11.json (drivers top {len(standings_out['drivers'])}, constructors top {len(standings_out['constructors'])})")
print(f"Wrote belgian_gp_2023_results.json ({len(results_out)} results)")
