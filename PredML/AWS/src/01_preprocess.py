import pandas as pd
from config import RAW_FILE, PROCESSED_FILE, ensure_dirs, banner
import numpy as np

def preprocess_data():
    ensure_dirs()  # Ensure directories exist
    banner("Stage 1: Preprocessing(data cleaning) Raw Data")  # Print a banner/visual
    df = pd.read_csv(RAW_FILE, keep_default_na=False, na_values=[""])  # Read raw data
    print(f"loaded raw data from {RAW_FILE} with {len(df)} rows")

    # 1. Types
    df["date"] = pd.to_datetime(df["date"])

    # 2. Missing Values: Fill missing sales with median sales for that product and region
    n_missing_before = df["sales"].isna().sum()
    df["sales"] = df.groupby(["product_id", "region"])["sales"].transform(
        lambda x: x.fillna(x.median())
    )
    n_missing_after = df["sales"].isna().sum()
    print(f"Filled missing sales values: {n_missing_before - n_missing_after}")

    # 3. Outliers: Cap actual_cost at 99th percentile for each product and region
    cap = df["actual_cost"].quantile(0.995)
    n_caps = (df["actual_cost"] > cap).sum()
    print(f"Capped {n_caps} outliers in actual_cost at 99.5th percentile ({cap:.2f})")
    df["actual_cost"] = df["actual_cost"].clip(upper=cap)

    print(f"Saving preprocessed data to {PROCESSED_FILE}")

    # 4. Duplicate Removal: Remove duplicates based on date, product_id, and region
    before = len(df)
    df = df.drop_duplicates(subset=["date", "product_id", "region"])
    after = len(df)
    print(f"Removed {before - after} duplicate rows")

    # 5. Sort - critical for lag features in next stage

    df = df.sort_values(by=["product_id", "region", "date"]).reset_index(drop=True) # Sort by product_id, region, and date to ensure correct order for lag features

    df.to_parquet(PROCESSED_FILE, index=False)
    print(f"Preprocessed data saved to {PROCESSED_FILE} with {len(df)} rows")
    print(f" Rows: {len(df)} | Columns: {list(df.columns)}")

if __name__ == "__main__":
    preprocess_data()