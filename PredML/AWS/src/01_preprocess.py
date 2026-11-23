import pandas as pd
import numpy as np

from config import (
    OPS_REVIEW_FILE,
    RAW_FILE,
    PROCESSED_FILE,
    ensure_dirs,
    banner,
)


def _write_ops_review(issues: pd.DataFrame) -> None:
    # Keep rejected rows in a separate file so Ops can correct the source data.
    if not issues.empty:
        issues.to_csv(OPS_REVIEW_FILE, index=False)
        print(
            f"Ops review required for {len(issues)} data-quality issue(s): "
            f"{OPS_REVIEW_FILE}"
        )


def preprocess_data():
    # Create output directories before reading or writing any pipeline files.
    ensure_dirs()
    banner("Stage 1: Preprocessing(data cleaning) Raw Data")
    # Treat empty strings as missing values while preserving other CSV values.
    df = pd.read_csv(RAW_FILE, keep_default_na=False, na_values=[""])
    print(f"loaded raw data from {RAW_FILE} with {len(df)} rows")

    # 1. Convert dates to datetime so sorting and downstream date features work.
    df["date"] = pd.to_datetime(df["date"])

    # 2. Handle missing values.
    # actual_cost is the model target, so it must come from Ops and is never
    # fabricated through imputation.
    issues = []
    missing_cost = df["actual_cost"].isna()
    if missing_cost.any():
        cost_issues = df.loc[missing_cost].copy()
        cost_issues["issue_type"] = "missing_actual_cost"
        cost_issues["required_action"] = (
            "Ops must verify and provide actual_cost before model training"
        )
        issues.append(cost_issues)
        df = df.loc[~missing_cost].copy()
        print(
            f"Excluded {missing_cost.sum()} row(s) with missing actual_cost; "
            "these rows must be corrected by Ops before retraining."
        )

    # sales is an input feature, so fill missing values with the median sales
    # for the same product and region across the available input dataset.
    n_missing_before = df["sales"].isna().sum()
    df["sales"] = df.groupby(["product_id", "region"])["sales"].transform(
        lambda x: x.fillna(x.median())
    )
    n_missing_after = df["sales"].isna().sum()
    print(f"Filled missing sales values: {n_missing_before - n_missing_after}")

    # A group with no non-missing sales has no trustworthy median. Send those
    # rows to Ops instead of silently assigning an arbitrary value.
    missing_sales = df["sales"].isna()
    if missing_sales.any():
        sales_issues = df.loc[missing_sales].copy()
        sales_issues["issue_type"] = "missing_sales_without_group_median"
        sales_issues["required_action"] = (
            "Ops must provide sales; no product-region median was available"
        )
        issues.append(sales_issues)
        df = df.loc[~missing_sales].copy()
        print(
            f"Excluded {missing_sales.sum()} row(s) with missing sales and no "
            "product-region median; Ops review is required."
        )

    _write_ops_review(pd.concat(issues, ignore_index=True) if issues else pd.DataFrame())
    if df.empty:
        raise ValueError("No valid rows remain after missing-value validation.")

    # 3. Limit extreme actual_cost values so unusual observations do not
    # dominate training. Missing costs were removed above before this step.
    cap = df["actual_cost"].quantile(0.995)
    n_caps = (df["actual_cost"] > cap).sum()
    print(f"Capped {n_caps} outliers in actual_cost at 99.5th percentile ({cap:.2f})")
    df["actual_cost"] = df["actual_cost"].clip(upper=cap)

    print(f"Saving preprocessed data to {PROCESSED_FILE}")

    # 4. Keep one record for each date/product/region combination.
    before = len(df)
    df = df.drop_duplicates(subset=["date", "product_id", "region"])
    after = len(df)
    print(f"Removed {before - after} duplicate rows")

    # 5. Sort chronologically within each product and region. The next stage
    # uses this order to calculate lag and rolling features correctly.
    df = df.sort_values(
        by=["product_id", "region", "date"]
    ).reset_index(drop=True)

    df.to_parquet(PROCESSED_FILE, index=False)
    print(f"Preprocessed data saved to {PROCESSED_FILE} with {len(df)} rows")
    print(f" Rows: {len(df)} | Columns: {list(df.columns)}")

if __name__ == "__main__":
    preprocess_data()