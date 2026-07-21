"""
Quick test script for the race-craft recommendation layer.
Run from project root: python test_race_craft.py
"""
import pandas as pd
from src.strategy.recommend_action import StrategyEngine

df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)
real_pit_durations = df.loc[df["pit_duration_ms"] > 0, "pit_duration_ms"]
engine = StrategyEngine(avg_pit_loss_ms=real_pit_durations.median())

# Pick one real race + lap, show the FULL field's race-craft recommendations
race_id = df["raceId"].sample(1, random_state=11).iloc[0]
lap_num = 30
field_df = df[(df["raceId"] == race_id) & (df["lap"] == lap_num)]

print(f"race={race_id} lap={lap_num}, field size={len(field_df)}\n")
for _, row in field_df.sort_values("position").iterrows():
    result = engine.recommend_full(row, same_lap_field_df=field_df)
    print(f"pos={row['position']:>2} driver={row['driverId']:<5} "
          f"win%={result['current_win_probability']:>5.1f}  "
          f"pit=[{result['pit_recommendation']}]  "
          f"drs=[{result['drs_recommendation']}]  "
          f"ers=[{result['ers_recommendation']}]  "
          f"race_craft=[{result['race_craft_recommendation']}]")