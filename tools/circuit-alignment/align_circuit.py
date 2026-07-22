"""
tools/circuit-alignment/align_circuit.py

Reusable version of the one-off Spa pipeline: pulls real corner + sector-boundary
coordinates from FastF1, registers them onto a julesr0y/f1-circuits-svg circuit
outline via a corner-based similarity fit, and writes a JSON file the Next.js
CircuitTrack component can consume directly.

Usage:
    python align_circuit.py --year 2023 --event Bahrain --slug bahrain \
        --svg ../../assets/circuits-svg/circuits/detailed/white-outline/bahrain-1.svg

--slug must match an id in assets/circuits-svg/circuits.json (used only for
logging). --svg is the path to the specific layout file for the CURRENT era of
that circuit (check circuits.json's `layouts` array for the right -N suffix).
--event is whatever FastF1 accepts for fastf1.get_session(year, event, 'R')
(country name, race name, or round number all work).

Output: web/src/data/circuits/<slug>.json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import fastf1
import fastf1.mvapi as mvapi
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "cache_fastf1"
OUT_DIR = ROOT / "web" / "src" / "data" / "circuits"
NODE_SCRIPT = Path(__file__).resolve().parent / "extract_svg_corners.js"


def fit_similarity(src, dst):
    """Umeyama similarity fit (rotation/reflection + scale + translation), src -> dst."""
    mu_src, mu_dst = src.mean(0), dst.mean(0)
    src_c, dst_c = src - mu_src, dst - mu_dst
    cov = dst_c.T @ src_c / len(src)
    U, S, Vt = np.linalg.svd(cov)
    R = U @ Vt
    var_src = (src_c ** 2).sum() / len(src)
    scale = S.sum() / var_src
    t = mu_dst - scale * R @ mu_src
    return lambda pts: (scale * (R @ pts.T)).T + t


def best_alignment(fastf1_corners, svg_corners):
    """Brute-force every cyclic shift x direction, keep the lowest-residual fit,
    then refit using only the well-matched (non-clustered) corners as anchors."""
    n = len(fastf1_corners)
    best = None
    for direction in (1, -1):
        reordered = fastf1_corners[::direction]
        for shift in range(n):
            cand = np.roll(reordered, shift, axis=0)
            transform = fit_similarity(cand, svg_corners)
            pred = transform(cand)
            resid = np.sqrt(((pred - svg_corners) ** 2).sum(axis=1)).mean()
            if best is None or resid < best[0]:
                best = (resid, cand)
    _, cand = best
    transform = fit_similarity(cand, svg_corners)
    pred = transform(cand)
    errs = np.linalg.norm(pred - svg_corners, axis=1)
    keep = errs <= np.percentile(errs, 65)
    robust_transform = fit_similarity(cand[keep], svg_corners[keep])
    robust_pred = robust_transform(cand)
    residual_all = float(np.sqrt(((robust_pred - svg_corners) ** 2).sum(axis=1)).mean())
    return robust_transform, residual_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--event", required=True, help="FastF1 event identifier (name, country, or round number)")
    ap.add_argument("--slug", required=True, help="circuits.json id, used for output filename + logging")
    ap.add_argument("--svg", required=True, help="path to the current-era layout SVG for this circuit")
    ap.add_argument("--num-corners", type=int, default=None,
                     help="Override the corner count used for SVG curvature detection. "
                          "Defaults to whatever FastF1 reports as this circuit's real corner count.")
    args = ap.parse_args()

    CACHE_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    print(f"[{args.slug}] loading session {args.year} {args.event} R ...")
    session = fastf1.get_session(args.year, args.event, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    circuit_key = session.session_info["Meeting"]["Circuit"]["Key"]
    info = mvapi.get_circuit_info(year=args.year, circuit_key=circuit_key)
    fastf1_corners = info.corners[["X", "Y"]].to_numpy(dtype=float)
    num_corners = args.num_corners or len(fastf1_corners)
    print(f"[{args.slug}] fetched {len(fastf1_corners)} real corners (circuit_key={circuit_key}); "
          f"using num_corners={num_corners} for SVG curvature detection")

    fastest = session.laps.pick_fastest()
    import fastf1.api as api
    pos = api.position_data(session.api_path)
    df = pos[fastest["DriverNumber"]]
    df = df[df["Status"] == "OnTrack"].reset_index(drop=True)

    def nearest_xy(t):
        idx = (df["Time"] - t).abs().idxmin()
        return np.array([float(df.loc[idx, "X"]), float(df.loc[idx, "Y"])])

    s1s2_real = nearest_xy(fastest["Sector1SessionTime"])
    s2s3_real = nearest_xy(fastest["Sector2SessionTime"])
    print(f"[{args.slug}] real sector boundaries: S1/S2={s1s2_real}, S2/S3={s2s3_real}")

    node_result = subprocess.run(
        ["node", str(NODE_SCRIPT), "--svg", args.svg, "--corners", str(num_corners)],
        capture_output=True, text=True, check=True,
    )
    svg_data = json.loads(node_result.stdout)
    svg_corners = np.array([[c["x"], c["y"]] for c in svg_data["corners"]])
    print(f"[{args.slug}] extracted {len(svg_corners)} SVG-space corners from {args.svg}")

    if len(fastf1_corners) != len(svg_corners):
        print(f"[{args.slug}] WARNING: corner count mismatch (FastF1={len(fastf1_corners)}, "
              f"SVG={len(svg_corners)}) — alignment quality will be degraded.", file=sys.stderr)
        n = min(len(fastf1_corners), len(svg_corners))
        fastf1_corners, svg_corners = fastf1_corners[:n], svg_corners[:n]

    transform, residual = best_alignment(fastf1_corners, svg_corners)
    s1s2_svg = transform(s1s2_real.reshape(1, 2))[0]
    s2s3_svg = transform(s2s3_real.reshape(1, 2))[0]
    print(f"[{args.slug}] alignment residual: {residual:.1f}px")
    print(f"[{args.slug}] S1/S2 -> ({s1s2_svg[0]:.1f}, {s1s2_svg[1]:.1f})   "
          f"S2/S3 -> ({s2s3_svg[0]:.1f}, {s2s3_svg[1]:.1f})")

    out = {
        "slug": args.slug,
        "sourceEvent": {"year": args.year, "event": args.event},
        "pathD": svg_data["pathD"],
        "numCorners": num_corners,
        "residualPx": round(residual, 1),
        "sectorPoints": [
            [round(float(s1s2_svg[0]), 1), round(float(s1s2_svg[1]), 1)],
            [round(float(s2s3_svg[0]), 1), round(float(s2s3_svg[1]), 1)],
        ],
    }
    out_path = OUT_DIR / f"{args.slug}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"[{args.slug}] wrote {out_path}")


if __name__ == "__main__":
    main()
