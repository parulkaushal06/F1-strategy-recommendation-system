# Dashboard

`dashboard/app.py` — Streamlit app that ties the win-probability model and the
full strategy engine (`10_strategy_engine.md`) into one live view, answering
Objective 4.

## What it shows

- **Sidebar**: pick a season → race → driver, then a lap slider.
- **Top row**: current win probability, pit urgency score, tire age, and a
  recommendation checklist (pit, DRS, ERS, race craft), matching the original
  project spec's mock dashboard layout.
- **Win probability trend**: a line chart of this driver's predicted win
  probability across every lap raced so far this session.
- **Full field table**: every driver's position, win probability, pit status,
  DRS, and race-craft call for the selected lap — gives race-craft context
  (e.g. seeing that the car ahead in the table is also under threat from
  behind).
- **Feature importance (expandable)**: answers Objective 1 (what actually
  drives winning) directly in the dashboard, not just in `09_model_results.md`.

## Important framing choice: this replays real races, it isn't live

There's no live telemetry feed wired into this project — see
`06_known_limitations.md`. Rather than pretend otherwise, the dashboard is
explicit (in the sidebar caption and the footer) that it **replays a real
historical race lap by lap**, computing every number (win probability, gaps,
recommendations) exactly the way it would be computed from a live feed. The
only difference is the race already happened. This keeps the same standard
of honesty as the ERS/DRS proxy labeling elsewhere in the project — better to
be upfront than let someone assume it's connected to a live broadcast feed.

## Running it

```bash
pip install streamlit plotly
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501` by default.

## Design notes

- `st.cache_data` / `st.cache_resource` used so the ~93MB cleaned dataset and
  the model only load once per session, not on every slider move.
- The field table calls `engine.recommend_full()` once per driver on the
  selected lap (typically ~20 drivers) — fast enough for interactive use
  since it's all in-memory pandas/sklearn inference, no external calls.
- Chart library is Plotly (already common in the Python data stack and
  interactive by default) rather than matplotlib, for a cleaner iteration
  experience inside Streamlit.