# Dashboard and API

The frontend is a Next.js 16 / React 19 / TypeScript app in `web/`. It calls the FastAPI service in `src/api/main.py` over HTTP and receives JSON. The browser never loads model pickle files.

```text
web/src/app pages → web/src/lib/api.ts → NEXT_PUBLIC_API_URL
                                      → FastAPI routes → dataset/model/StrategyEngine
```

The API loads the cleaned dataset, feature list, and calibrated model at startup. It also loads the raw model for global feature importance and lazy SHAP construction. CORS origins are controlled by `RACECRAFT_CORS_ORIGINS` (local defaults are ports 3000 and 3100).

## Pages

- **Home** (`web/src/app/page.tsx`): static 2023 calendar/standings data, with API lookup for race details.
- **Race Hub** (`web/src/app/race-hub/page.tsx`): race selection and circuit/session information; uses the API and local circuit data.
- **Strategy** (`web/src/app/strategy/page.tsx`): season/race/driver/lap selection, probability history, replay, recommendation cards, field table, what-if controls, feature importance, and optional model metrics.
- **Compare** (`web/src/app/compare/page.tsx`): two drivers' current state and probability histories for a selected race.
- **Results** (`web/src/app/results/page.tsx`): static 2023 Belgian GP results JSON.

The dashboard is a historical replay, not a live timing client. SHAP is available at the API endpoint but is not currently shown in the frontend.

## API routes

| Route | Purpose |
|---|---|
| `/health` | Liveness response; GET and HEAD |
| `/api/seasons`, `/api/races`, `/api/race-info`, `/api/drivers`, `/api/laps` | Dataset lookups |
| `/api/strategy` | Driver state, history, full field, recommendations, feature importance |
| `/api/compare` | Two-driver comparison |
| `/api/simulate/pit-timings` | Pit timing options |
| `/api/simulate/what-if` | Combined pit/push/attack/DRS/overtake scenarios |
| `/api/explain` | Per-row SHAP explanation |
| `/api/model-metrics` | Reads saved `models/model_metrics.json` |

FastAPI's interactive docs are at `/docs` when the backend is running.

## Run locally

From the repository root, with required ignored data and model artifacts present:

```bash
uvicorn src.api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd web
npm ci
npm run dev
```

Open `http://localhost:3000`. The API client defaults to `http://localhost:8000`; configure `NEXT_PUBLIC_API_URL` in `web/.env.local` to use another backend.

## Deployment

The root Dockerfile and `render.yaml` deploy the API. `start.sh` downloads the ignored data/model bundle from `DATA_URL` if required files are missing. Configure `RACECRAFT_CORS_ORIGINS` to include the deployed frontend origin. The frontend deployment needs `NEXT_PUBLIC_API_URL` set to the backend address. GitHub Actions CI runs pytest and frontend lint, TypeScript checking, and build; `.github/workflows/cd.yml` is manually triggered.
