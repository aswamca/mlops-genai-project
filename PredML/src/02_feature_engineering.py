import pandas as pd

from config import PROCESSED_FILE, banner


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return clean transaction data with engineered features."""
    df = df.sort_values(["product_id", "region", "date"]).copy()

    # Lag features are calculated within each product and region.
    groups = df.groupby(["product_id", "region"])
    df["sales_lag_1d"] = groups["sales"].shift(1)
    df["sales_lag_7d"] = groups["sales"].shift(7)
    df["cost_lag_1d"] = groups["actual_cost"].shift(1)
    df["cost_sales_ratio_lag_7d"] = (
        groups["actual_cost"].shift(7) / df["sales_lag_7d"]
    )

    df["sales_rolling_7d_avg"] = groups["sales"].transform(
        lambda sales: sales.shift(1).rolling(window=7, min_periods=1).mean()
    )

    df["month"] = df["date"].dt.month
    df["quater"] = df["date"].dt.quarter
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_q4"] = df["month"].isin([10, 11, 12]).astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_month_end"] = df["date"].dt.is_month_end.astype(int)

    encoded_columns = {
        "product_id": "product_id_enc",
        "region": "region_enc",
        "category": "catagory_enc",
    }
    for column, encoded_column in encoded_columns.items():
        df[encoded_column] = pd.factorize(df[column].astype(str), sort=True)[0]

    return df.dropna().reset_index(drop=True)


def run() -> pd.DataFrame:
    banner("STAGE 2 - FEATURE ENGINEERING")
    df = pd.read_parquet(PROCESSED_FILE)
    print(f"Loaded clean data: {len(df)} rows")

    df_features = build_features(df)
    print(f"After lag/rolling (dropped NaN warmup rows): {len(df_features)} rows")
    print(f"Feature columns: {[column for column in df_features.columns if column not in df.columns]}")
    print("\nFeature engineering complete (in-memory)")
    print("The next stage will persist these features.")
    return df_features


if __name__ == "__main__":
    run()