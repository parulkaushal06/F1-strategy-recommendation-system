"""
tune_drs_threshold.py

The original drs_zone_proxy used a fixed, GUESSED threshold (gap_to_ahead_ms
<= 1000, i.e. within 1 second). Now that real DRS ground truth exists for
2 races, this script empirically tests a RANGE of thresholds against that
ground truth and reports the recall/false-positive-rate trade-off for each,
instead of trusting the original guess.

Reuses the data loading and lap-bucketing logic from validate_drs_proxy.py
rather than duplicating it -- run that script first to confirm it works,
then run this one from the same project root.

IMPORTANT CAVEAT (stated honestly, not hidden): this is tuned against only
2 races (2,161 rows). Whatever threshold looks best here should be treated
as a reasonable estimate, not a guaranteed optimum for the full season --
there isn't enough real ground truth data to rule out overfitting to these
2 specific circuits. This is noted in the output and should be noted in
docs/06_known_limitations.md if a new threshold is adopted.

Run from project root:
    python tune_drs_threshold.py
"""
import sys

import pandas as pd

sys.path.insert(0, ".")
from validate_drs_proxy import (
    CAR_DATA_DIR, CLEANED_PATH, bucket_telemetry_into_laps,
    load_laps_timing, summarize_per_lap,
)
from src.data.final_merge import build_driver_map
import glob
import os

THRESHOLDS_MS = [500, 750, 1000, 1250, 1500, 2000, 2500]


def main():
    print("Loading raw car_data and lap timing (same as validate_drs_proxy.py)...")
    car_data_files = glob.glob(os.path.join(CAR_DATA_DIR, "*_car_data.csv"))
    car_data = pd.concat([pd.read_csv(f) for f in car_data_files], ignore_index=True)
    laps = load_laps_timing()

    print("Bucketing telemetry into laps (takes a minute)...")
    bucketed = bucket_telemetry_into_laps(car_data, laps)
    per_lap_real = summarize_per_lap(bucketed)

    driver_map = build_driver_map()
    per_lap_real = per_lap_real.merge(driver_map, on="driver_number", how="left")
    per_lap_real = per_lap_real.dropna(subset=["driverId"])
    per_lap_real["driverId"] = per_lap_real["driverId"].astype(int)

    df = pd.read_csv(CLEANED_PATH, low_memory=False)
    target_circuits = ["Bahrain International Circuit", "Autódromo José Carlos Pace"]
    scoped = df[(df["year"] == 2023) & (df["circuit_name"].isin(target_circuits))]
    race_id_map = scoped[["raceId", "circuit_name"]].drop_duplicates()

    session_to_circuit = {"bahrain_sakhir": "Bahrain International Circuit",
                           "brazil_interlagos": "Autódromo José Carlos Pace"}
    car_data_race_label = car_data[["session_key", "race_label"]].drop_duplicates()
    car_data_race_label["circuit_name"] = car_data_race_label["race_label"].map(session_to_circuit)
    session_to_race = car_data_race_label.merge(race_id_map, on="circuit_name", how="left")

    per_lap_real = per_lap_real.merge(session_to_race[["session_key", "raceId"]], on="session_key", how="left")
    per_lap_real = per_lap_real.dropna(subset=["raceId"])
    per_lap_real["raceId"] = per_lap_real["raceId"].astype(int)
    per_lap_real = per_lap_real.rename(columns={"lap_number": "lap"})

    # Pull the RAW continuous gap value (not the pre-binarized drs_zone_proxy flag)
    # so we can test different thresholds against it.
    merged = per_lap_real.merge(
        df[["raceId", "driverId", "lap", "gap_to_ahead_ms"]],
        on=["raceId", "driverId", "lap"], how="inner",
    )
    print(f"\nFinal matched rows: {len(merged)}\n")

    real = merged["real_eligible_or_on"].astype(bool)
    gap = merged["gap_to_ahead_ms"].abs()

    print(f"{'Threshold (ms)':>15} | {'Agreement':>10} | {'Recall':>8} | {'False Pos Rate':>15}")
    print("-" * 60)
    results = []
    for threshold in THRESHOLDS_MS:
        proxy = gap <= threshold
        agreement = (proxy == real).mean() * 100
        recall = (proxy & real).sum() / max(real.sum(), 1) * 100
        fpr = (proxy & ~real).sum() / max((~real).sum(), 1) * 100
        results.append({"threshold_ms": threshold, "agreement": agreement, "recall": recall, "fpr": fpr})
        print(f"{threshold:>15} | {agreement:>9.1f}% | {recall:>7.1f}% | {fpr:>14.1f}%")

    results_df = pd.DataFrame(results)
    best_agreement = results_df.loc[results_df["agreement"].idxmax()]
    print(f"\nBest overall agreement: {best_agreement['threshold_ms']:.0f}ms "
          f"({best_agreement['agreement']:.1f}% agreement, "
          f"{best_agreement['recall']:.1f}% recall, {best_agreement['fpr']:.1f}% FPR)")

    print("\nCAVEAT: tuned against only 2 races (2,161 rows). Treat as a reasonable")
    print("estimate, not a guaranteed season-wide optimum -- see the docstring above.")


if __name__ == "__main__":
    main()