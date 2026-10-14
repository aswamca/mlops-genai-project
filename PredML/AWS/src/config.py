"""AWS/SageMaker configuration shared by the AWS stage scripts.

All durable data and model state is stored in S3.  The local implementation
under ``PredML/src`` intentionally keeps its filesystem-backed configuration.
Raw input data is uploaded to S3 before the AWS pipeline starts.
"""

from __future__ import annotations

import os

import fsspec


AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "ap-southeast-2"))
S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_PREFIX = os.environ.get("S3_PREFIX", "predml").strip("/")
if not S3_BUCKET:
    raise RuntimeError("S3_BUCKET is required for the AWS stage scripts.")

S3_ROOT = f"s3://{S3_BUCKET}/{S3_PREFIX}" if S3_PREFIX else f"s3://{S3_BUCKET}"


def s3_path(*parts: str) -> str:
    """Build an S3 URI below the configured project prefix."""
    clean_parts = [str(part).strip("/") for part in parts if str(part).strip("/")]
    return "/".join([S3_ROOT.rstrip("/"), *clean_parts])


def s3_exists(path: str) -> bool:
    return fsspec.core.url_to_fs(path)[0].exists(fsspec.core.url_to_fs(path)[1])


def s3_glob(directory: str, pattern: str) -> list[str]:
    """Return matching S3 URIs in deterministic order."""
    fs, key = fsspec.core.url_to_fs(directory)
    matches = fs.glob(f"{key.rstrip('/')}/{pattern}")
    protocol = fs.protocol[0] if isinstance(fs.protocol, (tuple, list)) else fs.protocol
    return sorted(f"{protocol}://{match}" for match in matches)


def read_text(path: str, encoding: str = "utf-8") -> str:
    with fsspec.open(path, mode="rt", encoding=encoding) as stream:
        return stream.read()


def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    with fsspec.open(path, mode="wt", encoding=encoding) as stream:
        stream.write(content)


def ensure_dirs() -> None:
    """Compatibility hook; S3 prefixes are created by object writes."""


def banner(msg: str, char: str = "=") -> None:
    print(f"\n{char * 72}\n{msg}\n{char * 72}")


DATA_PREFIX = "data"
RAW_DIR = s3_path(DATA_PREFIX, "01_raw")
PROCESSED_DIR = s3_path(DATA_PREFIX, "02_processed")
FEATURE_STORE = s3_path(DATA_PREFIX, "03_features_store")
OFFLINE_STORE = s3_path(DATA_PREFIX, "03_features_store", "offline")
ONLINE_STORE = s3_path(DATA_PREFIX, "03_features_store", "online")

REGISTRY_DIR = s3_path("model", "registry", "cost_forecaster")
PRODUCTION_VERSION_FILE = s3_path("model", "registry", "cost_forecaster", "production_version.txt")
PREDICTIONS_DIR = s3_path("predictions", "batch")
BASELINE_DIR = s3_path("monitoring", "baseline")
REPORTS_DIR = s3_path("monitoring", "reports")

MLFLOW_URI = os.environ.get(
    "MLFLOW_TRACKING_URI",
    os.environ.get("SAGEMAKER_MLFLOW_TRACKING_URI", ""),
)
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "pharmacy_cost_forecasting_aws")
MLFLOW_REGISTERED_MODEL_NAME = os.environ.get("MLFLOW_REGISTERED_MODEL_NAME", "cost_forecaster")
MLFLOW_ARTIFACTS = os.environ.get("MLFLOW_ARTIFACTS", f"{S3_ROOT}/mlflow-artifacts")
CHAMPION_ALIAS = "champion"
PREVIOUS_ALIAS = "previous"

RAW_FILE = s3_path(DATA_PREFIX, "01_raw", "raw_data_pharma_transactions.csv")
PROCESSED_FILE = s3_path(DATA_PREFIX, "02_processed", "transactions_clean.parquet")
OFFLINE_FILE = s3_path(DATA_PREFIX, "03_features_store", "offline", "features.parquet")
ONLINE_FILE = s3_path(DATA_PREFIX, "03_features_store", "online", "latestr_features.json")
PRODUCT_MASTER_FILE = s3_path(DATA_PREFIX, "product_master.json")

PRODUCTS = [
    ("PRD001", "Entresto", "Cardiovascular", 180_000, 0.28),
    ("PRD002", "Cosentyx", "Immunology", 220_000, 0.32),
    ("PRD003", "Kisqali", "Oncology", 160_000, 0.35),
    ("PRD004", "Jardiance", "Diabetes", 200_000, 0.30),
    ("PRD005", "Dupixent", "Immunology", 250_000, 0.33),
    ("PRD006", "Trulicity", "Diabetes", 190_000, 0.29),
    ("PRD007", "Imbruvica", "Oncology", 170_000, 0.34),
    ("PRD008", "Xeljanz", "Immunology", 210_000, 0.31),
    ("PRD009", "Farxiga", "Diabetes", 180_000, 0.28),
    ("PRD010", "Revlimid", "Oncology", 80_000, 0.38),
]
REGIONS = ["NA", "EU", "APAC", "LATAM"]
DATA_START_DATE = "2024-01-01"
DATA_END_DATE = "2025-12-31"
TARGET_COLUMN = "actual_cost"
FEATURE_COLUMNS = [
    "sales", "sales_lag_1d", "sales_lag_7d", "sales_rolling_7d_avg",
    "cost_lag_1d", "cost_sales_ratio_lag_7d", "month", "quater",
    "day_of_week", "is_q4", "is_weekend", "is_month_end",
    "product_id_enc", "region_enc", "catagory_enc",
]
TEST_DAYS = 60
XGBOOST_PARAMS = {
    "learning_rate": 0.02, "max_depth": 6, "subsample": 0.85,
    "colsample_bytree": 0.85, "n_estimators": 2000, "colsample_bylevel": 0.85,
    "min_child_weight": 3, "reg_alpha": 0.3, "reg_lambda": 2.5,
    "gamma": 0.1, "random_state": 7, "n_jobs": -1,
}
DRIFT_THRESHOLDS = {
    "missing_rate_max": 0.05, "mean_shift_pct": 0.20, "std_shift_pct": 0.30,
    "prediction_shift_pct": 0.30, "psi_threshold": 0.20, "new_category_alert": True,
}
