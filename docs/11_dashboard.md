# Dashboard — RACECRAFT (Next.js + FastAPI)

`web/` (Next.js + TypeScript + Tailwind) talks to `src/api/main.py` (FastAPI),
which wraps the win-probability model and `StrategyEngine` — this is the
project's single dashboard, answering Objective 4.

## Design history

The first working dashboard was a Streamlit app (`dashboard/app.py`), built
to validate that the strategy engine's output was actually usable in a live,
lap-by-lap UI before investing in a full frontend. Once that was confirmed,
it was replaced with this full-stack app and removed from the repo — one
frontend, one backend, rather than maintaining two UIs against the same
engine. `docs/07_project_status.md` keeps the historical record of that
change.

## Architecture

```
web/ (Next.js)  --HTTP-->  src/api/main.py (FastAPI)  -->  StrategyEngine + model
```

The frontend can't load a `.pkl` file itself (it runs in the browser), so the
FastAPI layer is a thin wrapper: it loads the model, feature list, and
`StrategyEngine` once at startup, and exposes them as JSON endpoints
(`/api/seasons`, `/api/races`, `/api/drivers`, `/api/laps`, `/api/strategy`,
`/api/compare`). See `src/api/main.py` for the full endpoint list.

## Pages

- **Home / Season Hub** (`web/src/app/page.tsx`) — season overview, current
  project status pills, standings snapshot.
- **Race Hub** (`web/src/app/race-hub/page.tsx`) — pick a season and race,
  see the real circuit map for that track (see "Circuit maps" below).
- **Strategy** (`web/src/app/strategy/page.tsx`) — the core dashboard: pick a
  driver, scrub through the race lap by lap, see live win probability, pit
  urgency score, tire age, and the full pit/DRS/ERS/race-craft recommendation
  set from `StrategyEngine.recommend_full()`, alongside the circuit map and
  the full-field table for that lap.
- **Compare** (`web/src/app/compare/page.tsx`) — two drivers side by side,
  win-probability trend lines for both across the same race.
- **Results** (`web/src/app/results/page.tsx`) — static race result reference
  page.

## Important framing choice: this replays real races, it isn't live

There's no live telemetry feed wired into this project — see
`06_known_limitations.md`. Rather than pretend otherwise, the app is explicit
that it **replays a real historical race lap by lap**, computing every number
(win probability, gaps, recommendations) exactly the way it would be computed
from a live feed. The only difference is the race already happened. This
keeps the same standard of honesty as the ERS/DRS proxy labeling elsewhere in
the project — better to be upfront than let someone assume it's connected to
a live broadcast feed.

## Circuit maps

31 of the 35 circuits in this project's dataset have **real, not
illustrative** track outlines (traced by
[julesr0y/f1-circuits-svg](https://github.com/julesr0y/f1-circuits-svg),
CC BY 4.0 — see `assets/circuits-svg/ATTRIBUTION.md`), with corners and
sector-boundary markers registered onto that outline using real FastF1
telemetry (`tools/circuit-alignment/`). Alignment quality is honestly
reported per circuit (residual ~20–100px depending on how geometrically
distinct the track's corners are). 4 circuits (Valencia, Korea, India,
Malaysia) have no real map — FastF1 doesn't reliably expose session data for
races before ~2018, so this needs a different data source, not just re-running
the existing alignment pipeline.

## Running it

```bash
# Terminal 1 — the API (real model + StrategyEngine)
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — the frontend
cd web
npm install
npm run dev
```

Opens at `http://localhost:3000`. The API must be running first — the
frontend calls `http://localhost:8000` directly by default, configurable via
`web/.env.local` (`NEXT_PUBLIC_API_URL`).

## Design notes

- The model, feature list, and dataset load **once at FastAPI startup**, not
  per-request — same intent as the caching the earlier Streamlit prototype
  used, just at the process level instead of per-session.
- `/api/strategy`'s full-field table calls `StrategyEngine.recommend_batch()`
  once for the whole field rather than looping `recommend_full()` per driver
  — see the note in `src/api/main.py` and `09_model_results.md` for the
  speed impact this had.
- CORS is currently restricted to `localhost:3000`/`3100` in
  `src/api/main.py` — this needs to become environment-driven before
  deploying anywhere public (see `12_industrial_roadmap.md` for the full
  deployment checklist).