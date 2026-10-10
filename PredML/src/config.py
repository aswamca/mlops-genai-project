from pathlib import Path

# ROOT PATHS
BASE_DIR = Path(__file__).resolve().parent.parent

# Data layer
RAW_DIR = BASE_DIR / "data" / "01_raw"
PROCESSED_DIR = BASE_DIR / "data" / "02_processed"
FEATURE_STORE = BASE_DIR / "data" / "03_features_store"
OFFLINE_STORE = FEATURE_STORE / "offline"
ONLINE_STORE = FEATURE_STORE / "online"

#Model artifacts

REGISTRY_DIR = BASE_DIR / "model" / "registry" / "cost_forecaster"
PRODUCTION_VERSION_FILE  = REGISTRY_DIR / "production_version.txt"

# Predictions

PREDICTIONS_DIR = BASE_DIR / "predictions" / "batch"

# Monitoring (simulates a real-time monitoring system sagemaker model monitor)
BASELINE_DIR = BASE_DIR / "monitoring" / "baseline"
REPORTS_DIR = BASE_DIR / "monitoring" / "reports"

# MLFlow tracking (experiment tracking)

MLFLOW_DIR = BASE_DIR / "mlruns"
MLFLOW_DB = MLFLOW_DIR / "mlruns.db"

# MLFLOW_TRACKING_URI env var wins when set (docker compose set it to http://mlflow:5000).
# this let conatiner talk to the mlflow server container. When running locally, we use sqlite db file.

import os as _os
MLFLOW_URI = _os.environ.get("MLFLOW_TRACKING_URI") or f"sqlite:///{MLFLOW_DB.as_posix()}"

MLFLOW_ARTIFACTS= "mlflow-artifacts:/" if MLFLOW_URI.startswith("http") else f"file:///{(MLFLOW_DIR / 'artifacts').as_posix()}"
MLFLOW_EXPERIMENT = _os.environ.get(
    "MLFLOW_EXPERIMENT",
    "pharmacy_cost_forecasting",
)

MLFLOW_REGISTERED_MODEL_NAME = "cost_forecaster"
CHAMPION_ALIAS = "champion"
PREVIOUS_ALIAS = "previous"

# FILE NAMES
RAW_FILE = RAW_DIR / "raw_data_pharma_transactions.csv"
PROCESSED_FILE = PROCESSED_DIR / "transactions_clean.parquet"
OFFLINE_FILE = OFFLINE_STORE / "features.parquet"
ONLINE_FILE = ONLINE_STORE / "latestr_features.json"

# prodcut master file - governance/catalogue file
PRODUCT_MASTER_FILE = BASE_DIR / "data" / "product_master.json" # read by stage 7 at inference to answer "is this sku legit?" and "what is the product name for this sku?"

# BUSINESS: PHARMA PRODUCTS
PRODUCTS = [
    # (product_id,name, catagory, base_sales, cost_ratio)
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

# Data generation window ( 2 years of daily data --> 29K rows)
DATA_START_DATE = "2024-01-01"
DATA_END_DATE = "2025-12-31"

# ML Configurations
TARGET_COLUMN = "actual_cost"
FEATURE_COLUMNS = ["sales", "sales_lag_1d", "sales_lag_7d", "sales_rolling_7d_avg",
                   "cost_lag_1d", "cost_sales_ratio_lag_7d",
                   "month","quater","day_of_week","is_q4","is_weekend","is_month_end",
                   "product_id_enc", "region_enc", "catagory_enc",
                   ]

# Train/test split configuration last 60 days as test set
TEST_DAYS = 60

XGBOOST_PARAMS = {
    "learning_rate": 0.02,
    "max_depth": 6,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "n_estimators": 2000,
    "colsample_bylevel": 0.85,
    "min_child_weight": 3,
    "reg_alpha": 0.3,
    "reg_lambda": 2.5,
    "gamma": 0.1,
    "random_state": 7,
    "n_jobs": -1,
}

# Monitoring configuration thresholds for alerting -  stage 8 uses these thresholds to trigger alerts when the model performance degrades
DRIFT_THRESHOLDS = {
    "missing_rate_max": 0.05,  # 5% missing values in features
    "mean_shift_pct": 0.20,
    "std_shift_pct": 0.30,
    "prediction_shift_pct": 0.30,
    "psi_threshold": 0.20,
    "new_category_alert": True,  # 5% new categories in categorical features
}

# HELPERS FUNCTIONS
def ensure_dirs():
    """Ensure that all required directories exist."""
    for directory in [RAW_DIR, PROCESSED_DIR, FEATURE_STORE, OFFLINE_STORE, ONLINE_STORE,
                      REGISTRY_DIR, PREDICTIONS_DIR, BASELINE_DIR, REPORTS_DIR, MLFLOW_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

def banner(msg: str, char: str = "="):
    print(f"\n{char * 72}\n{msg}\n{char * 72}")