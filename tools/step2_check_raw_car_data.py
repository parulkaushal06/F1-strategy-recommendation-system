"""
step2_check_raw_car_data.py

Read-only inspection script -- makes no changes to any file.
Run from the project root:
    python step2_check_raw_car_data.py
"""
import os
import pandas as pd

RAW_DIR = "data/raw/openf1_car_data"

if not os.path.isdir(RAW_DIR):
    print(f"FOLDER NOT FOUND: {RAW_DIR}")
    print("Checking what folders exist under 'data/raw' instead:")
    print(os.listdir("data/raw"))
else:
    files = os.listdir(RAW_DIR)
    print(f"=== Files inside {RAW_DIR} ===")
    for f in files:
        path = os.path.join(RAW_DIR, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f" - {f}  ({size_mb:.1f} MB)")

    if files:
        sample_path = os.path.join(RAW_DIR, files[0])
        print(f"\n=== Sample from first file: {files[0]} ===")
        sample = pd.read_csv(sample_path, nrows=5)
        print(sample.columns.tolist())
        print(sample.head())

        if "drs" in sample.columns:
            print("\n=== Real 'drs' column values (full file) ===")
            full = pd.read_csv(sample_path)
            print(full["drs"].value_counts())