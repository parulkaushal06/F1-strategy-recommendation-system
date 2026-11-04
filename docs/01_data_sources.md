# Data sources and coverage

The project combines historical race tables with a limited telemetry enrichment. Source datasets are local artifacts under ignored `data/`; they are not committed with the code.

## Ergast/Kaggle tables

The Kaggle mirror supplies CSVs under `data/raw/ergast/`, including races, results, drivers, constructors, circuits, lap times, pit stops, qualifying, and status. The current modeling table is filtered to seasons from 2011 because earlier lap timing is sparse or inconsistent. Ergast provides the base lap-by-lap position and timing history, outcome labels, and identity metadata.

## OpenF1

The scripts in `src/data/fetch_openf1*.py` target the 2023 race season. They collect session metadata, driver mappings, laps, pit stops, stints, weather, and selected high-frequency car telemetry for DRS validation. Data is joined where race, driver, and lap identities can be matched. Enrichment is concentrated in 2023 and does not cover every row or telemetry field.

OpenF1 driver identity is bridged using the three-letter driver code. Race identity uses circuit-name normalization and explicit overrides in `src/data/final_merge.py`. Revalidate these joins when source files or seasons change.

## FastF1 and circuit visuals

FastF1 is used by circuit-alignment tooling to align corner and sector information. Circuit outline SVGs come from the attributed `assets/circuits-svg/` collection. Attribution and license details are in that directory's `ATTRIBUTION.md` and `LICENSE`.

## Scope and caveats

- The saved cleaned dataset contains 320,274 lap-level rows covering 2011–2024; the saved model evaluation tests on 2024.
- OpenF1 telemetry is enrichment, not a complete replacement for the historical base table. Missing values are expected for most rows.
- DRS telemetry was collected for a small validation sample, not a season-wide inference feed.
- No public ground-truth ERS deployment data is included.
- The dashboard replays historical races and does not consume a live timing feed.

See [collection](02_data_collection.md), [merging](03_data_merging.md), and [limitations](06_known_limitations.md).
