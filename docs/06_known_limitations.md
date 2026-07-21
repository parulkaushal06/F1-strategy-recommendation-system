# Known Limitations

Being explicit about these strengthens the project rather than weakening it — it shows
the difference between what's measured and what's inferred was understood deliberately,
not overlooked.

## 1. No real ERS (Energy Recovery System) data exists publicly

F1 teams do not release ERS deployment mode data — this is proprietary strategy
information. **No public data source, including OpenF1, has this.** Any "Use ERS
Overtake Mode" recommendation this project produces is inferred from proxy signals
(e.g., throttle/speed patterns on straights), not ground-truth team telemetry. This is
stated clearly in both the dashboard output and this documentation.

## 2. DRS status is a rule-based proxy for 99.6% of the dataset

Real DRS activation data exists in OpenF1's `car_data` endpoint, but was only fetched
for 3 races (Bahrain, Monza, Interlagos) due to its size (see `01_data_sources.md`).
For the remaining 320,274 − ~few thousand rows, `drs_zone_proxy` is a rule-based
estimate (`gap_to_ahead_ms <= 1000`, i.e. within 1 second of the car ahead) — a
reasonable approximation of DRS *eligibility*, not confirmed activation.

**Validation plan**: compare `drs_zone_proxy` against real DRS status from the 3
validated races to report an agreement percentage — turning this limitation into a
measured, reported accuracy rather than an unverified assumption.

## 3. OpenF1 telemetry coverage is sparse relative to the full dataset

Only ~0.4% of rows (1,357 out of 320,274) have real OpenF1 enrichment, because OpenF1
only covers the 2023 season, and only sessions that successfully matched during the
race-ID bridging step. The win-probability model is trained on the full Ergast dataset
(which doesn't depend on OpenF1), while the strategy engine's real-telemetry validation
is necessarily scoped to this smaller, richer subset.

## 4. Lap-level timing data is unreliable before 2011

Ergast's `lap_times.csv` has sparse/inconsistent coverage for older seasons. This
project filters to `year >= 2011` during feature engineering for this reason — earlier
seasons are excluded from lap-level modeling (though still present in aggregate
results data if needed for other analysis).

## 5. Team-name and naming convention differences between sources

Ergast and OpenF1 use different naming conventions for the same real-world entity (e.g.
"Alpine" vs "Alpine F1 Team"). This was checked and confirmed to be a labeling
difference, not a data error (see `04_data_cleaning.md`, section 4).

## 6. One 2023 race (Emilia Romagna GP / Imola) has no OpenF1-Ergast match

This is correct, not a bug — the race was cancelled due to flooding and does not appear
in the 2023 Ergast results at all.