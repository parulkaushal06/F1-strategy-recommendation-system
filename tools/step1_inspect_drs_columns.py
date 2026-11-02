"""
step1_inspect_drs_columns.py

Read-only inspection script -- makes no changes to any file.
Run from the project root:
    python step1_inspect_drs_columns.py
"""
import pandas as pd

df = pd.read_csv("data/processed/cleaned_dataset.csv", low_memory=False)

print("=== Total rows:", len(df), "===\n")

print("=== All columns containing 'drs' or 'openf1' ===")
drs_related = [c for c in df.columns if "drs" in c.lower() or "openf1" in c.lower()]
for c in drs_related:
    print(" -", c)

print("\n=== has_openf1_telemetry value counts ===")
print(df["has_openf1_telemetry"].value_counts())

telemetry_df = df[df["has_openf1_telemetry"] == 1]
print(f"\n=== Rows with real telemetry: {len(telemetry_df)} ===")

for c in drs_related:
    if c == "drs_zone_proxy":
        continue
    print(f"\n--- Sample values for '{c}' (real telemetry rows only) ---")
    print(telemetry_df[c].value_counts(dropna=False).head(15))

print("\n=== raceIds present in these rows (should be our validated races) ===")
print(telemetry_df["raceId"].unique())
print(telemetry_df["circuit_name"].unique())