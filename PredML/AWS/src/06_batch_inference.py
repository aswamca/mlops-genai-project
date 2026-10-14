import json

import mlflow
import numpy as np
import pandas as pd

from config import (
    FEATURE_COLUMNS,
    MLFLOW_REGISTERED_MODEL_NAME,
    OFFLINE_FILE,
    PREDICTIONS_DIR,
    TARGET_COLUMN,
    TEST_DAYS,
    banner,
    ensure_dirs,
    s3_path,
)
from mlflow_registry import load_champion_model


def load_production_model():
    """Load the champion model and its feature contract from MLflow."""
    model_version = load_champion_model()
    feature_columns = json.loads(model_version.tags.get("feature_columns", "[]"))
    if not feature_columns:
        raise RuntimeError(
            f"Champion version {model_version.version} has no feature_columns tag."
        )

    model_uri = f"models:/{MLFLOW_REGISTERED_MODEL_NAME}@{model_version.aliases[0]}"
    model = mlflow.pyfunc.load_model(model_uri)
    metrics = {
        name: float(model_version.tags[name])
        for name in (
            "train_mape",
            "test_mape",
            "train_rmse",
            "test_rmse",
            "train_r2",
            "test_r2",
        )
        if name in model_version.tags
    }
    metadata = {
        "metrics": metrics,
        "run_id": model_version.tags.get("run_id"),
        "role": model_version.tags.get("role"),
    }
    return str(model_version.version), model, feature_columns, metadata


def run() -> pd.DataFrame:
    ensure_dirs()
    banner("STAGE 6 - BATCH INFERENCE")

    version, model, feature_columns, metadata = load_production_model()
    print(f"Loaded production model: {MLFLOW_REGISTERED_MODEL_NAME} v{version}")
    print(f"Training metrics: {metadata['metrics']}")

    missing_features = [
        column for column in feature_columns if column not in FEATURE_COLUMNS
    ]
    if missing_features:
        raise ValueError(
            f"Champion expects features not configured by this project: {missing_features}"
        )

    df = pd.read_parquet(OFFLINE_FILE).sort_values("date")
    cutoff = df["date"].max() - pd.Timedelta(days=TEST_DAYS)
    batch = df[df["date"] > cutoff].copy()
    if batch.empty:
        raise ValueError("No rows found in the requested inference window.")

    print(
        f"Scoring {len(batch)} rows from {batch['date'].min().date()} "
        f"to {batch['date'].max().date()}"
    )
    batch["predicted_cost"] = model.predict(batch[feature_columns])
    batch["error"] = batch["predicted_cost"] - batch[TARGET_COLUMN]
    denominator = np.maximum(batch[TARGET_COLUMN].abs().to_numpy(), np.finfo(float).eps)
    batch["abs_pct_error"] = batch["error"].abs().to_numpy() / denominator

    output_columns = [
        "date",
        "product_id",
        "product_name",
        "region",
        "sales",
        TARGET_COLUMN,
        "predicted_cost",
        "error",
        "abs_pct_error",
    ]
    output = batch[output_columns].copy()
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output_file = s3_path("predictions", "batch", f"predictions_{timestamp}.csv")
    output.to_csv(output_file, index=False)

    print(f"\nPredictions written to: {output_file}")
    print(f"Rows: {len(output)}")
    print(f"Mean predicted cost: {output['predicted_cost'].mean():.2f}")
    print(f"Mean actual cost: {output[TARGET_COLUMN].mean():.2f}")
    print(f"MAPE (this batch): {output['abs_pct_error'].mean():.4f}")
    print("\nSample:")
    print(output.head(5).to_string(index=False))
    return output


if __name__ == "__main__":
    run()