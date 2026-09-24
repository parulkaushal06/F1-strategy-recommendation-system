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

## 2. DRS status is a rule-based proxy, now validated against real telemetry

Real DRS activation data exists in OpenF1's `car_data` endpoint, but was only fetched
for **2 races** (Bahrain, Brazil/Interlagos — an earlier version of this document said
3 races including Monza; only 2 `car_data` files actually exist in `data/raw/openf1_car_data/`,
this has been corrected). For the remaining ~99.3% of the dataset, `drs_zone_proxy` is a
rule-based estimate (`gap_to_ahead_ms <= 1000`, i.e. within 1 second of the car ahead) — an
approximation of DRS *eligibility*, not confirmed activation.

**Validation results** (see `validate_drs_proxy.py`): real DRS telemetry (sampled at
~3.7 Hz) was bucketed into laps using each lap's start timestamp, then compared against
`drs_zone_proxy` for the same (raceId, driverId, lap) across 2,161 matched rows from the
2 validated races. Real DRS codes follow OpenF1's documented mapping: 0/1 = off, 8 =
detected/eligible (in a DRS zone, gap < 1s, not yet activated), 10/12/14 = actually on.

| Comparison | Agreement | Recall | False positive rate |
|---|---|---|---|
| Proxy vs. real "eligible or on" (code 8/10/12/14) | 78.1% | 54.1% | 13.5% |
| Proxy vs. real "actually on" (code 10/12/14) | 78.6% | 55.2% | 13.5% |

**Honest read of this result**: the proxy is not overconfident (a 13.5% false positive
rate is fairly low — when it says "no DRS," it's usually right), but it misses close to
half of real DRS activations (54-55% recall). The most likely cause: real DRS eligibility
is decided by the gap at a **fixed detection point** on track (just before the DRS zone),
checked once per lap at that exact location, whereas `drs_zone_proxy` uses whatever
`gap_to_ahead_ms` value is stored for that lap in the per-lap dataset — a looser,
whole-lap approximation rather than a check at the real detection point. This is a
genuine, now-measured limitation of the proxy, not an assumption.

## 3. OpenF1 telemetry coverage is sparse relative to the full dataset

~7.3% of rows (23,431 out of 320,274) have real OpenF1 enrichment (updated after
fixing a `session_key` merge bug that had originally limited this to ~0.4% —
see `04_data_cleaning.md`), because OpenF1 only covers the 2023 season, and only
sessions that successfully matched during the race-ID bridging step. The
win-probability model is trained on the full Ergast dataset (which doesn't depend on
OpenF1), while the strategy engine's real-telemetry validation is necessarily scoped
to this smaller, richer subset.

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

---

**Note on scope**: an earlier version of this document had an item 7 here
("homepage hero hardcoded to Belgian GP"). That was a plain frontend bug —
fixable code, not a structural constraint of the data or approach — and
didn't actually belong in a "known limitations" document, which is meant
for things that can't simply be fixed (proxy accuracy, data coverage gaps,
etc.). It's since been fixed; see `07_project_status.md` for the record of
that change. Keeping this note rather than silently deleting the history,
in the same spirit as the rest of this document.