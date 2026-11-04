# Known limitations

These constraints describe the current data and implementation, not necessarily permanent properties of future versions.

## Data and coverage

- The local cleaned snapshot and saved evaluation cover through 2024. OpenF1 collection scripts target 2023; telemetry enrichment is sparse (about 7% of cleaned rows) and some requests/joins may be missing.
- Lap-level modeling filters to 2011 onward because earlier lap timing is less complete.
- Cross-source joins depend on driver codes and circuit-name overrides. New source seasons require checking those mappings and duplicate keys.
- DRS ground truth was fetched for a small two-race sample, so validation results may not generalize to all circuits or years.
- Circuit traces are available only for circuits represented in the frontend registry; other tracks show a fallback.

## Model

- Production training currently uses data before 2023 for training, 2023 for isotonic calibration, and 2024 as the held-out test year. It cannot train from a dataset missing either fixed year without updating `src/features/train_model.py`.
- Calibration on one season does not guarantee calibration in another. Saved 2024 bucket analysis shows some upper probability ranges are overconfident.
- Each driver's probability is predicted independently. Probabilities across the field are not normalized to sum to 100%.
- Position, grid, and gaps account for much of the predictive signal. The model is not evidence that telemetry features or the strategy rules independently improve decisions.
- SHAP contributions explain the raw tree model; the headline score is from the separately calibrated model, so contributions do not add up to the calibrated probability.

## Recommendations and simulations

- There is no public ERS deployment ground truth; ERS advice is a proxy.
- DRS eligibility is approximated from per-lap gap, not the exact official detection point or confirmed activation.
- Pit urgency and race-craft calls use transparent heuristics. They are not trained policies or counterfactual race simulations.
- A pit what-if applies median pit-loss data plus simplified pace/tire feature changes. Pit timing scenarios do not simulate the full race or traffic evolution.
- Push assumes a 150 ms/lap pace gain; attack assumes 800 ms gap closure. These are illustrative assumptions, clearly labeled in responses.
- DRS flips the trained proxy flag; overtake assumes a pass completes and modifies the row's position/gaps. These are model input perturbations, not physical race simulations.

## Product and deployment

- The dashboard replays historical laps; it is not connected to live timing, weather, or team telemetry.
- Home uses a static 2023 season/calendar and standings snapshot; Results is a static 2023 Belgian GP table. Strategy, Compare, and Race Hub use the API for their race data.
- SHAP explanations are served by the API but are not displayed in the UI.
- Data and model pickle files are gitignored. API startup requires these artifacts and Ergast lookup CSVs. Render deployment needs a reachable `DATA_URL` bundle and correct CORS/frontend URL settings.
- A free hosting tier may sleep and take time to wake; the frontend retries selected server/network failures.

See [model results](09_model_results.md), [strategy engine](10_strategy_engine.md), and [dashboard](11_dashboard.md) for implementation details.
