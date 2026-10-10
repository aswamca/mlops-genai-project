from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from config import (
    FEATURE_COLUMNS,
    MLFLOW_REGISTERED_MODEL_NAME,
    OFFLINE_FILE,
    PREDICTIONS_DIR,
    PRODUCTS,
    REGIONS,
    banner,
    ensure_dirs,
)
from mlflow_registry import load_champion_model


FREQ_MAP = {
    "daily": "D",
    "weekly": "W-SUN",
    "monthly": "M",
    "quarterly": "Q",
    "half": "2Q",
    "yearly": "Y",
}
GROWTH_FACTOR = 1.05
SALES_PLAN_COLUMNS = {"date", "product_id", "region", "sales"}


def load_production_model() -> tuple[str, mlflow.pyfunc.PyFuncModel, list[str]]:
    """Load the champion model and its recorded feature contract."""
    model_version = load_champion_model()
    feature_columns_raw = model_version.tags.get("feature_columns")
    if not feature_columns_raw:
        raise RuntimeError(
            f"Champion version {model_version.version} has no feature_columns tag. "
            "Run 04_train_model.py and 05_register_model.py first."
        )
    try:
        feature_columns = json.loads(feature_columns_raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Champion version {model_version.version} has invalid feature_columns JSON."
        ) from error
    if (
        not isinstance(feature_columns, list)
        or not feature_columns
        or any(not isinstance(column, str) for column in feature_columns)
    ):
        raise RuntimeError(
            f"Champion version {model_version.version} has an invalid feature_columns tag."
        )
    unsupported = [column for column in feature_columns if column not in FEATURE_COLUMNS]
    if unsupported:
        raise RuntimeError(
            f"Champion model requires unsupported project features: {unsupported}"
        )

    model_uri = f"models:/{MLFLOW_REGISTERED_MODEL_NAME}/{model_version.version}"
    model = mlflow.pyfunc.load_model(model_uri)
    return str(model_version.version), model, feature_columns


def _parse_dates(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_date = pd.Timestamp(date.fromisoformat(start))
        end_date = pd.Timestamp(date.fromisoformat(end))
    except ValueError as error:
        raise ValueError("Start and end dates must use YYYY-MM-DD format.") from error
    if start_date > end_date:
        raise ValueError(f"Start date {start_date.date()} is after end date {end_date.date()}.")
    return start_date, end_date


def _load_sales_plan(path: str | Path | None) -> pd.DataFrame | None:
    if path is None:
        return None
    sales_plan_path = Path(path)
    if not sales_plan_path.is_file():
        raise FileNotFoundError(f"Sales plan CSV does not exist: {sales_plan_path}")
    try:
        sales_plan = pd.read_csv(sales_plan_path, parse_dates=["date"])
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read sales plan CSV {sales_plan_path}: {error}") from error

    missing_columns = SALES_PLAN_COLUMNS.difference(sales_plan.columns)
    if missing_columns:
        raise ValueError(
            f"Sales plan is missing required columns: {sorted(missing_columns)}"
        )
    sales_plan = sales_plan[list(SALES_PLAN_COLUMNS)].copy()
    sales_plan["date"] = pd.to_datetime(sales_plan["date"], errors="coerce").dt.normalize()
    if sales_plan["date"].isna().any():
        raise ValueError("Sales plan contains invalid dates; expected YYYY-MM-DD.")
    sales_plan["product_id"] = sales_plan["product_id"].astype(str).str.strip()
    sales_plan["region"] = sales_plan["region"].astype(str).str.strip()
    sales_plan["sales"] = pd.to_numeric(sales_plan["sales"], errors="coerce")
    if (
        sales_plan["product_id"].eq("").any()
        or sales_plan["region"].eq("").any()
        or sales_plan["sales"].isna().any()
        or not np.isfinite(sales_plan["sales"].to_numpy(dtype=float)).all()
        or sales_plan["sales"].lt(0).any()
    ):
        raise ValueError("Sales plan contains blank keys or invalid/negative sales values.")
    if sales_plan.duplicated(["date", "product_id", "region"]).any():
        raise ValueError("Sales plan must have at most one row per date, product_id, and region.")
    return sales_plan


def project_sales(
    future_dates: pd.DatetimeIndex,
    product_id: str,
    region: str,
    offline_df: pd.DataFrame,
    growth_factor: float = GROWTH_FACTOR,
) -> list[float]:
    """Project sales from the same calendar day last year, or the SKU-region mean."""
    history = offline_df.loc[
        (offline_df["product_id"] == product_id)
        & (offline_df["region"] == region),
        ["date", "sales"],
    ].copy()
    history["date"] = pd.to_datetime(history["date"]).dt.normalize()
    history = history.dropna(subset=["sales"]).sort_values("date")
    if history.empty:
        raise ValueError(f"No sales history available for {product_id}|{region}.")

    same_day_last_year = {
        timestamp.normalize(): float(sales)
        for timestamp, sales in zip(history["date"], history["sales"])
    }
    fallback = float(history["sales"].mean())
    projected: list[float] = []
    for future_date in future_dates:
        try:
            prior_year_date = future_date - pd.DateOffset(years=1)
            baseline = same_day_last_year.get(prior_year_date.normalize(), fallback)
        except (OverflowError, ValueError):
            baseline = fallback
        projected.append(max(0.0, baseline * growth_factor))
    return projected


def build_future_features(
    future_date: pd.Timestamp,
    sales: float,
    sales_history: list[float],
    cost_history: list[float],
    last_history_row: pd.Series,
) -> dict[str, float]:
    """Build one date's feature row using observations plus previous forecasts."""
    sales_lag_1d = sales_history[-1] if sales_history else sales
    sales_lag_7d = sales_history[-7] if len(sales_history) >= 7 else sales_lag_1d
    cost_lag_1d = cost_history[-1] if cost_history else 0.0
    cost_lag_7d = cost_history[-7] if len(cost_history) >= 7 else cost_lag_1d
    rolling_sales = sales_history[-7:] if sales_history else [sales]
    cost_sales_ratio_lag_7d = (
        cost_lag_7d / sales_lag_7d if sales_lag_7d > 0 else 0.35
    )

    row: dict[str, float] = {
        "sales": float(sales),
        "sales_lag_1d": float(sales_lag_1d),
        "sales_lag_7d": float(sales_lag_7d),
        "sales_rolling_7d_avg": float(np.mean(rolling_sales)),
        "cost_lag_1d": float(cost_lag_1d),
        "cost_sales_ratio_lag_7d": float(cost_sales_ratio_lag_7d),
        "month": float(future_date.month),
        "quater": float((future_date.month - 1) // 3 + 1),
        "day_of_week": float(future_date.dayofweek),
        "is_q4": float(future_date.month in (10, 11, 12)),
        "is_weekend": float(future_date.dayofweek >= 5),
        "is_month_end": float(future_date.is_month_end),
        "product_id_enc": float(last_history_row["product_id_enc"]),
        "region_enc": float(last_history_row["region_enc"]),
        "catagory_enc": float(last_history_row["catagory_enc"]),
    }
    return row


def _periodize(daily: pd.DataFrame, frequency: str) -> pd.DataFrame:
    daily = daily.copy()
    period_frequency = {
        "daily": "D",
        "weekly": "W-SUN",
        "monthly": "M",
        "quarterly": "Q",
        "half": "2Q",
        "yearly": "Y",
    }[frequency]
    daily["period"] = daily["date"].dt.to_period(period_frequency)
    grouped = (
        daily.groupby(["period", "product_id", "region"], as_index=False)
        .agg(
            predicted_cost=("predicted_cost", "sum"),
            predicted_sales=("sales", "sum"),
            days_in_period=("date", "nunique"),
        )
    )
    grouped["period_start"] = grouped["period"].dt.start_time.dt.normalize()

    if frequency == "quarterly":
        grouped["label"] = grouped["period"].astype(str)
    elif frequency == "half":
        year = grouped["period_start"].dt.year.astype(str)
        half = ((grouped["period_start"].dt.quarter - 1) // 2 + 1).astype(str)
        grouped["label"] = year + "-H" + half
    elif frequency == "yearly":
        grouped["label"] = grouped["period_start"].dt.year.astype(str)
    elif frequency == "weekly":
        grouped["label"] = grouped["period_start"].dt.strftime("%G-W%V")
    elif frequency == "monthly":
        grouped["label"] = grouped["period_start"].dt.strftime("%Y-%m")
    else:
        grouped["label"] = grouped["period_start"].dt.strftime("%Y-%m-%d")

    return grouped[
        [
            "period_start",
            "label",
            "product_id",
            "region",
            "predicted_cost",
            "predicted_sales",
            "days_in_period",
        ]
    ].sort_values(["period_start", "product_id", "region"]).reset_index(drop=True)


def forecast(
    frequency: str,
    start: str,
    end: str,
    products: list[str] | None = None,
    regions: list[str] | None = None,
    sales_plan_path: str | Path | None = None,
) -> pd.DataFrame:
    """Forecast daily costs, then aggregate to the requested reporting frequency."""
    if frequency not in FREQ_MAP:
        raise ValueError(f"frequency must be one of {list(FREQ_MAP)}.")
    ensure_dirs()
    start_date, end_date = _parse_dates(start, end)
    future_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    selected_products = products if products is not None else [row[0] for row in PRODUCTS]
    selected_regions = regions if regions is not None else REGIONS
    if not selected_products or not selected_regions:
        raise ValueError("At least one product and one region must be selected.")
    unknown_products = sorted(set(selected_products).difference(row[0] for row in PRODUCTS))
    unknown_regions = sorted(set(selected_regions).difference(REGIONS))
    if unknown_products:
        raise ValueError(f"Unknown products: {unknown_products}")
    if unknown_regions:
        raise ValueError(f"Unknown regions: {unknown_regions}")

    banner(f"STAGE 9 - FORECAST ({frequency.upper()}) {start_date.date()} -> {end_date.date()}")
    version, model, feature_columns = load_production_model()
    print(f"Using champion model version: {version}")

    offline_df = pd.read_parquet(OFFLINE_FILE)
    required_history_columns = {
        "date",
        "product_id",
        "region",
        "sales",
        "actual_cost",
        "product_id_enc",
        "region_enc",
        "catagory_enc",
    }
    missing_history_columns = required_history_columns.difference(offline_df.columns)
    if missing_history_columns:
        raise ValueError(
            f"Offline feature store is missing columns: {sorted(missing_history_columns)}"
        )
    offline_df["date"] = pd.to_datetime(offline_df["date"], errors="coerce").dt.normalize()
    if offline_df["date"].isna().any():
        raise ValueError("Offline feature store contains invalid dates.")
    future_features = {
        "sales_lag_1d",
        "sales_lag_7d",
        "sales_rolling_7d_avg",
        "cost_lag_1d",
        "cost_sales_ratio_lag_7d",
        "month",
        "quater",
        "day_of_week",
        "is_q4",
        "is_weekend",
        "is_month_end",
    }
    unavailable_features = set(feature_columns).difference(
        set(offline_df.columns).union(future_features)
    )
    if unavailable_features:
        raise ValueError(
            "Model features cannot be built from the offline store or forecast dates: "
            f"{sorted(unavailable_features)}"
        )

    sales_plan = _load_sales_plan(sales_plan_path)
    combinations: list[dict[str, object]] = []
    for product_id in selected_products:
        for region in selected_regions:
            history = offline_df.loc[
                (offline_df["product_id"] == product_id)
                & (offline_df["region"] == region)
            ].sort_values("date")
            if history.empty:
                raise ValueError(f"No offline history for {product_id}|{region}.")
            latest_date = history["date"].max()
            if start_date <= latest_date:
                raise ValueError(
                    f"Forecast start {start_date.date()} must be after the latest "
                    f"history date {latest_date.date()} for {product_id}|{region}."
                )
            history = history.dropna(subset=["sales", "actual_cost"])
            if history.empty:
                raise ValueError(f"No complete sales/cost history for {product_id}|{region}.")

            sales_values = pd.to_numeric(history["sales"], errors="coerce").to_numpy(dtype=float)
            cost_values = pd.to_numeric(history["actual_cost"], errors="coerce").to_numpy(dtype=float)
            valid = np.isfinite(sales_values) & np.isfinite(cost_values)
            history = history.loc[valid]
            sales_values = sales_values[valid].tolist()
            cost_values = cost_values[valid].tolist()
            if history.empty:
                raise ValueError(f"No finite sales/cost history for {product_id}|{region}.")

            projected_sales = project_sales(
                future_dates,
                product_id,
                region,
                offline_df,
            )
            if sales_plan is not None:
                product_plan = sales_plan.loc[
                    (sales_plan["product_id"] == product_id)
                    & (sales_plan["region"] == region)
                ].set_index("date")["sales"]
                projected_sales = [
                    float(product_plan.loc[future_date])
                    if future_date in product_plan.index
                    else projected
                    for future_date, projected in zip(future_dates, projected_sales)
                ]
            combinations.append(
                {
                    "product_id": product_id,
                    "region": region,
                    "sales_history": sales_values,
                    "cost_history": cost_values,
                    "last_history_row": history.iloc[-1],
                    "projected_sales": projected_sales,
                }
            )

    daily_rows: list[dict[str, object]] = []
    for date_index, future_date in enumerate(future_dates):
        feature_rows: list[dict[str, float]] = []
        for combination in combinations:
            row = build_future_features(
                future_date=future_date,
                sales=combination["projected_sales"][date_index],
                sales_history=combination["sales_history"],
                cost_history=combination["cost_history"],
                last_history_row=combination["last_history_row"],
            )
            feature_rows.append(row)

        model_input = pd.DataFrame(feature_rows, columns=feature_columns)
        try:
            numeric_input = model_input.to_numpy(dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Could not construct model features for {future_date.date()}: {error}") from error
        if not np.isfinite(numeric_input).all():
            raise ValueError(f"Model feature rows contain non-finite values on {future_date.date()}.")
        predictions = np.asarray(model.predict(pd.DataFrame(numeric_input, columns=feature_columns)))
        if predictions.ndim != 1 or len(predictions) != len(combinations):
            raise RuntimeError(
                f"Model returned {predictions.shape} for {len(combinations)} forecast rows."
            )
        if not np.isfinite(predictions).all():
            raise RuntimeError(f"Model returned non-finite predictions on {future_date.date()}.")

        for combination, prediction, feature_row in zip(combinations, predictions, feature_rows):
            sales_value = feature_row["sales"]
            predicted_cost = float(prediction)
            combination["sales_history"].append(sales_value)
            combination["cost_history"].append(predicted_cost)
            daily_rows.append(
                {
                    "date": future_date,
                    "product_id": combination["product_id"],
                    "region": combination["region"],
                    "sales": sales_value,
                    "predicted_cost": predicted_cost,
                }
            )

    daily = pd.DataFrame(daily_rows)
    aggregated = _periodize(daily, frequency)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = PREDICTIONS_DIR / "forecast" / f"forecast_{frequency}_{timestamp}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    aggregated.to_csv(output_path, index=False)
    print(f"\nForecast written to: {output_path}")
    print(f"Daily rows scored: {len(daily)} | Aggregated rows: {len(aggregated)}")
    print(f"\n{frequency.upper()} SUMMARY (predicted cost):")
    summary = aggregated.groupby("label")["predicted_cost"].sum().sort_index()
    for label, total in summary.items():
        print(f"  {label}: {total:,.2f}")
    print(f"\nGrand total ({start_date.date()} -> {end_date.date()}): "
          f"{aggregated['predicted_cost'].sum():,.2f}")
    return aggregated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flexible future cost forecasting (daily through yearly)."
    )
    parser.add_argument(
        "--frequency",
        required=True,
        choices=list(FREQ_MAP),
        help="Aggregation granularity.",
    )
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD).")
    parser.add_argument(
        "--products",
        default=None,
        help="Comma-separated product IDs (defaults to all products).",
    )
    parser.add_argument(
        "--regions",
        default=None,
        help="Comma-separated regions (defaults to all regions).",
    )
    parser.add_argument(
        "--sales-plan",
        default=None,
        help="Optional CSV with date,product_id,region,sales columns.",
    )
    args = parser.parse_args()
    products = [value.strip() for value in args.products.split(",") if value.strip()] if args.products else None
    regions = [value.strip() for value in args.regions.split(",") if value.strip()] if args.regions else None
    forecast(
        frequency=args.frequency,
        start=args.start,
        end=args.end,
        products=products,
        regions=regions,
        sales_plan_path=args.sales_plan,
    )


if __name__ == "__main__":
    main()
