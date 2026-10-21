"""
Packs the files the deployed API needs (they are not in git) into one
racecraft-data.tar.gz, ready to upload as a GitHub Release asset.

Run from the project root, on the machine that has data/ and models/:
    python tools/make_data_bundle.py
"""
import argparse
import os
import sys
import tarfile
from importlib import metadata

FILES = [
    "data/processed/cleaned_dataset.csv",
    "data/raw/ergast/races.csv",
    "data/raw/ergast/drivers.csv",
    "models/win_probability_model_calibrated.pkl",
    "models/win_probability_model_raw.pkl",
    "models/feature_columns.pkl",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="project root (default: current folder)")
    parser.add_argument("--out", default="racecraft-data.tar.gz")
    args = parser.parse_args()

    missing = [f for f in FILES if not os.path.exists(os.path.join(args.root, f))]
    if missing:
        print("Missing files:")
        for f in missing:
            print("  -", f)
        print("Run the data pipeline / train_model.py first (see README.md).")
        return 1

    with tarfile.open(args.out, "w:gz") as tar:
        for f in FILES:
            tar.add(os.path.join(args.root, f), arcname=f)

    size_mb = os.path.getsize(args.out) / 1024 / 1024
    print(f"Created {args.out} ({size_mb:.1f} MB)")
    print("\nLocal library versions (pin scikit-learn in requirements-api.txt to match):")
    for pkg in ("scikit-learn", "numpy", "pandas", "shap", "joblib"):
        try:
            print(f"  {pkg}=={metadata.version(pkg)}")
        except metadata.PackageNotFoundError:
            print(f"  {pkg}: not installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())