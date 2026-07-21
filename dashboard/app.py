"""
dashboard/app.py

F1 Strategy & Win Probability Dashboard (Objective 4).

Ties together everything built in earlier steps:
  - win_probability_model.pkl  -> live win probability
  - StrategyEngine (recommend_full) -> pit / DRS / ERS / race-craft recommendations

IMPORTANT — what this dashboard actually shows: there's no live telemetry feed
in this project (see docs/06_known_limitations.md), so this simulates "real
time" by stepping lap-by-lap through a REAL historical race from the cleaned
dataset. Every number shown (win probability, gaps, recommendations) is
computed the same way it would be from a live feed — the only difference is
the race already happened. This is stated in the UI too, not just here.

Run from project root:
    streamlit run dashboard/app.py
"""

import os
import joblib
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.strategy.recommend_action import StrategyEngine

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "cleaned_dataset.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "win_probability_model.pkl")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "feature_columns.pkl")

st.set_page_config(page_title="F1 Strategy & Win Probability", page_icon="🏎️", layout="wide")


# ---------------------------------------------------------------------------
# Cached loaders — heavy objects load once per session, not on every rerun
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH, low_memory=False)
    return df


@st.cache_resource
def load_engine():
    real_pit_durations_path = DATA_PATH  # reuse df already loaded by load_data via caching
    df = load_data()
    real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
    avg_pit_loss_ms = real_pit_durations.median() if len(real_pit_durations) > 0 else 22000
    engine = StrategyEngine(model_path=MODEL_PATH, features_path=FEATURES_PATH,
                             avg_pit_loss_ms=avg_pit_loss_ms)
    return engine


@st.cache_resource
def load_model_and_features():
    model = joblib.load(MODEL_PATH)
    feature_cols = joblib.load(FEATURES_PATH)
    return model, feature_cols


df = load_data()
engine = load_engine()
model, feature_cols = load_model_and_features()

# ---------------------------------------------------------------------------
# Sidebar — pick a race, driver, and lap (this is the "real-time scrubber")
# ---------------------------------------------------------------------------
st.sidebar.title("🏎️ Race Selector")
st.sidebar.caption(
    "No live telemetry feed exists for this project — this replays a REAL "
    "historical race lap by lap, computing every number the same way a live "
    "feed would. See docs/06_known_limitations.md."
)

years = sorted(df["year"].unique(), reverse=True)
sel_year = st.sidebar.selectbox("Season", years)

year_df = df[df["year"] == sel_year]
race_options = (
    year_df[["raceId", "round", "circuit_name"]]
    .drop_duplicates()
    .sort_values("round")
)
race_labels = [f"Round {r} — {c}" for r, c in zip(race_options["round"], race_options["circuit_name"])]
race_choice = st.sidebar.selectbox("Race", race_labels)
sel_race_id = race_options.iloc[race_labels.index(race_choice)]["raceId"]

race_df = df[df["raceId"] == sel_race_id]

driver_options = race_df[["driverId", "driverRef", "code", "constructor_name"]].drop_duplicates()
driver_labels = [
    f"{code} — {ref} ({team})"
    for ref, code, team in zip(driver_options["driverRef"], driver_options["code"], driver_options["constructor_name"])
]
driver_choice = st.sidebar.selectbox("Driver", driver_labels)
sel_driver_id = driver_options.iloc[driver_labels.index(driver_choice)]["driverId"]

driver_race_df = race_df[race_df["driverId"] == sel_driver_id].sort_values("lap")
if driver_race_df.empty:
    st.error("No lap data for this driver in this race.")
    st.stop()

max_lap = int(driver_race_df["lap"].max())
total_laps = int(driver_race_df["total_laps"].iloc[0])
sel_lap = st.sidebar.slider("Current lap", min_value=1, max_value=max_lap, value=min(20, max_lap))

st.sidebar.markdown("---")
st.sidebar.caption(f"Race distance: {total_laps} laps · Data through lap {max_lap} for this driver")

# ---------------------------------------------------------------------------
# Current state for the selected driver + lap
# ---------------------------------------------------------------------------
current_row_df = driver_race_df[driver_race_df["lap"] == sel_lap]
if current_row_df.empty:
    st.warning("No data for this exact lap (may be a retirement/DNF lap). Try a lower lap number.")
    st.stop()
current_row = current_row_df.iloc[0]

field_df = race_df[race_df["lap"] == sel_lap]
result = engine.recommend_full(current_row, same_lap_field_df=field_df)

circuit_name = current_row["circuit_name"]
driver_code = current_row["code"]
team_name = current_row["constructor_name"]
position = int(current_row["position"])

st.title("🏎️ F1 Live Strategy Dashboard")
st.subheader(f"{circuit_name} · {sel_year} · Lap {sel_lap}/{total_laps} · {driver_code} ({team_name}) · P{position}")

# ---------------------------------------------------------------------------
# Top row: win probability + key recommendation checklist
# ---------------------------------------------------------------------------
col1, col2 = st.columns([1, 2])

with col1:
    st.metric("Current Win Probability", f"{result['current_win_probability']:.1f}%")
    st.metric("Pit Urgency Score", f"{result['pit_urgency_score']:.0f} / 100")
    st.metric("Tire Age", f"{result['laps_on_current_tires']} laps ({result['tire_age_ratio']*100:.0f}% of window)")

with col2:
    st.markdown("### Recommendations")

    def render_flag(label, value, positive_keywords):
        is_positive = any(k in value for k in positive_keywords)
        icon = "✅" if is_positive else "⚪"
        st.markdown(f"{icon} **{label}:** {value}")

    render_flag("Pit Stop", result["pit_recommendation"], ["PIT NOW", "CONSIDER PIT"])
    render_flag("DRS", result["drs_recommendation"], ["AVAILABLE"])
    render_flag("ERS", result["ers_recommendation"], ["OVERTAKE"])
    render_flag("Race Craft", result["race_craft_recommendation"], ["ATTACK", "DEFEND"])

    with st.expander("Model context: what if this driver pitted THIS lap?"):
        ctx = result["model_context_if_pit_now"]
        st.write(f"Simulated win probability if pitting now: **{ctx['simulated_win_probability']:.1f}%** "
                 f"(change: {ctx['probability_change']:+.1f} pts)")
        st.caption(ctx["note"])

st.markdown("---")

# ---------------------------------------------------------------------------
# Win probability trend across the race so far
# ---------------------------------------------------------------------------
st.markdown("### Win Probability Trend (this race, up to the current lap)")

history_df = driver_race_df[driver_race_df["lap"] <= sel_lap].copy()
X_hist = history_df[feature_cols].fillna(-999)
history_df["win_prob"] = model.predict_proba(X_hist)[:, 1] * 100

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=history_df["lap"], y=history_df["win_prob"],
    mode="lines+markers", name="Win probability",
    line=dict(color="#E10600", width=3),
))
fig.update_layout(
    xaxis_title="Lap", yaxis_title="Win probability (%)",
    yaxis_range=[0, 100], height=350,
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Full field snapshot for this lap — race-craft context
# ---------------------------------------------------------------------------
st.markdown(f"### Full Field — Lap {sel_lap}")

field_rows = []
for _, row in field_df.sort_values("position").iterrows():
    r = engine.recommend_full(row, same_lap_field_df=field_df)
    field_rows.append({
        "Pos": int(row["position"]),
        "Driver": row["code"],
        "Team": row["constructor_name"],
        "Win %": f"{r['current_win_probability']:.1f}",
        "Pit": r["pit_recommendation"].split(" (")[0],
        "DRS": "Yes" if "AVAILABLE" in r["drs_recommendation"] else "No",
        "Race Craft": r["race_craft_recommendation"].split(" (")[0],
    })

field_table = pd.DataFrame(field_rows)
st.dataframe(field_table, use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Feature importance — Objective 1 answer, shown for context
# ---------------------------------------------------------------------------
with st.expander("Objective 1: What actually drives winning? (model feature importance)"):
    importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False).head(10)
    fig2 = go.Figure(go.Bar(
        x=importances.values[::-1], y=importances.index[::-1], orientation="h",
        marker_color="#E10600",
    ))
    fig2.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20),
                        xaxis_title="Importance")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Position and gap-to-leader dominate — expected, since they're the most "
        "direct signal of race state. See docs/09_model_results.md for full analysis."
    )

st.caption(
    "⚠️ ERS recommendations are a proxy (no public source, including OpenF1, exposes real ERS "
    "deployment data). DRS beyond 3 validated races is a rule-based proxy too. "
    "See docs/06_known_limitations.md."
)