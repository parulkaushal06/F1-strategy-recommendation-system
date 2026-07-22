"""
Runs align_circuit.py for every circuit in the project's own dataset
(data/processed/cleaned_dataset.csv), using each circuit's most recent
appearance (best FastF1 coverage) and its current-era SVG layout from
assets/circuits-svg/circuits.json. Continues past failures (older seasons,
e.g. pre-2018, may have incomplete FastF1 timing data) and writes a summary.

Usage: python batch_align_all.py
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "circuits-svg"
ALIGN_SCRIPT = Path(__file__).resolve().parent / "align_circuit.py"
LOG_PATH = Path(__file__).resolve().parent / "batch_results.json"

# cleaned_dataset.csv circuit_name -> circuits.json slug (hand-verified, since
# name strings differ slightly between the two sources)
CIRCUIT_NAME_TO_SLUG = {
    "Albert Park Grand Prix Circuit": "melbourne",
    "Autodromo Enzo e Dino Ferrari": "imola",
    "Autodromo Internazionale del Mugello": "mugello",
    "Autodromo Nazionale di Monza": "monza",
    "Autódromo Hermanos Rodríguez": "mexico-city",
    "Autódromo Internacional do Algarve": "portimao",
    "Autódromo José Carlos Pace": "interlagos",
    "Bahrain International Circuit": "bahrain",
    "Baku City Circuit": "baku",
    "Buddh International Circuit": "buddh",
    "Circuit Gilles Villeneuve": "montreal",
    "Circuit Park Zandvoort": "zandvoort",
    "Circuit Paul Ricard": "paul-ricard",
    "Circuit de Barcelona-Catalunya": "catalunya",
    "Circuit de Monaco": "monaco",
    "Circuit de Spa-Francorchamps": "spa-francorchamps",
    "Circuit of the Americas": "austin",
    "Hockenheimring": "hockenheimring",
    "Hungaroring": "hungaroring",
    "Istanbul Park": "istanbul",
    "Jeddah Corniche Circuit": "jeddah",
    "Korean International Circuit": "yeongam",
    "Las Vegas Strip Street Circuit": "las-vegas",
    "Losail International Circuit": "lusail",
    "Marina Bay Street Circuit": "marina-bay",
    "Miami International Autodrome": "miami",
    "Nürburgring": "nurburgring",
    "Red Bull Ring": "spielberg",
    "Sepang International Circuit": "sepang",
    "Shanghai International Circuit": "shanghai",
    "Silverstone Circuit": "silverstone",
    "Sochi Autodrom": "sochi",
    "Suzuka Circuit": "suzuka",
    "Valencia Street Circuit": "valencia",
    "Yas Marina Circuit": "yas-marina",
}

# Already done in earlier one-off runs; skip by default (delete from here to redo).
ALREADY_DONE = {"spa-francorchamps", "bahrain", "silverstone", "monaco"}


def season_range_includes(season_str, year):
    for part in season_str.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            if int(lo) <= year <= int(hi):
                return True
        elif int(part) == year:
            return True
    return False


def find_layout_and_svg(slug, year):
    circuits = json.loads((ASSETS / "circuits.json").read_text(encoding="utf-8"))
    entry = next((c for c in circuits if c["id"] == slug), None)
    if entry is None:
        return None, None
    layout_id = None
    for layout in entry["layouts"]:
        if season_range_includes(layout["seasons"], year):
            layout_id = layout["layoutId"]
            break
    if layout_id is None:
        layout_id = entry["layouts"][-1]["layoutId"]  # fall back to most recent
    for variant_dir in ("detailed/white-outline", "minimal/white-outline"):
        svg_path = ASSETS / "circuits" / variant_dir / f"{layout_id}.svg"
        if svg_path.exists():
            return layout_id, svg_path
    return layout_id, None


def main():
    df = pd.read_csv(ROOT / "data" / "processed" / "cleaned_dataset.csv", low_memory=False,
                      usecols=["raceId", "year", "circuit_name"])
    latest = df.sort_values("year").drop_duplicates("circuit_name", keep="last")

    with open(ROOT / "data" / "raw" / "ergast" / "races.csv", encoding="utf-8") as f:
        race_names = {r["raceId"]: r["name"] for r in csv.DictReader(f)}

    jobs = []
    for row in latest.itertuples():
        slug = CIRCUIT_NAME_TO_SLUG.get(row.circuit_name)
        if slug is None:
            print(f"SKIP (no slug mapping): {row.circuit_name}")
            continue
        if slug in ALREADY_DONE:
            print(f"SKIP (already done): {slug}")
            continue
        layout_id, svg_path = find_layout_and_svg(slug, int(row.year))
        if svg_path is None:
            print(f"SKIP (no SVG file for {slug} layout {layout_id}): {row.circuit_name}")
            continue
        event_name = race_names.get(str(row.raceId), row.circuit_name)
        jobs.append({"slug": slug, "year": int(row.year), "event": event_name, "svg": str(svg_path)})

    print(f"\n{len(jobs)} circuits queued\n")

    results = []
    for i, job in enumerate(jobs, 1):
        print(f"=== [{i}/{len(jobs)}] {job['slug']} ({job['event']}, {job['year']}) ===")
        try:
            proc = subprocess.run(
                [sys.executable, str(ALIGN_SCRIPT),
                 "--year", str(job["year"]), "--event", job["event"],
                 "--slug", job["slug"], "--svg", job["svg"]],
                capture_output=True, text=True, timeout=300,
            )
            ok = proc.returncode == 0
            tail = "\n".join(proc.stdout.strip().splitlines()[-3:]) if ok else proc.stderr.strip()[-500:]
            print(tail)
            results.append({**job, "ok": ok, "detail": tail})
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT on {job['slug']}")
            results.append({**job, "ok": False, "detail": "timeout after 300s"})
        except Exception as e:
            print(f"ERROR on {job['slug']}: {e}")
            results.append({**job, "ok": False, "detail": str(e)})

    LOG_PATH.write_text(json.dumps(results, indent=2))
    succeeded = sum(r["ok"] for r in results)
    print(f"\n{succeeded}/{len(results)} succeeded. Full log: {LOG_PATH}")


if __name__ == "__main__":
    main()
