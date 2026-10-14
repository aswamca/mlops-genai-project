import json

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from mlflow.tracking import MlflowClient

from config import (
    FEATURE_COLUMNS,
    MLFLOW_EXPERIMENT,
    MLFLOW_REGISTERED_MODEL_NAME,
    MLFLOW_URI,
    OFFLINE_FILE,
    REGISTRY_DIR,
    TARGET_COLUMN,
    TEST_DAYS,
    XGBOOST_PARAMS,
    banner,
    ensure_dirs,
    write_text,
)


def _regression_metrics(actual: pd.Series, predicted: np.ndarray, prefix: str) -> dict:
    actual_values = actual.to_numpy(dtype=float)
    errors = actual_values - predicted
    denominator = np.maximum(np.abs(actual_values), np.finfo(float).eps)
    total_sum_squares = np.sum(np.square(actual_values - actual_values.mean()))
    r2 = (
        1.0 - np.sum(np.square(errors)) / total_sum_squares
        if total_sum_squares
        else 0.0
    )

    return {
        f"{prefix}_mape": float(np.mean(np.abs(errors) / denominator)),
        f"{prefix}_rmse": float(np.sqrt(np.mean(np.square(errors)))),
        f"{prefix}_r2": float(r2),
    }


def train() -> dict:
    ensure_dirs()
    banner("STAGE 4 - MODEL TRAINING (XGBoost + MLflow)")

    df = pd.read_parquet(OFFLINE_FILE).sort_values("date").reset_index(drop=True)
    print(f"Loaded features: {len(df)} rows")

    required_columns = ["date", TARGET_COLUMN, *FEATURE_COLUMNS]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Feature store is missing required columns: {missing_columns}")

    cutoff = df["date"].max() - pd.Timedelta(days=TEST_DAYS)
    train_df = df[df["date"] <= cutoff]
    test_df = df[df["date"] > cutoff]
    if train_df.empty or test_df.empty:
        raise ValueError("The time-based split produced an empty train or test set.")

    print(f"Train rows: {len(train_df)} through {cutoff.date()}")
    print(f"Test rows: {len(test_df)} after {cutoff.date()}")

    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]
    x_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    client = MlflowClient(tracking_uri=MLFLOW_URI)

    model_params = {
        **XGBOOST_PARAMS,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "early_stopping_rounds": 50,
    }

    with mlflow.start_run(
        run_name=f"xgboost-{pd.Timestamp.now():%Y%m%d-%H%M%S}"
    ) as run:
        mlflow.log_params(model_params)
        mlflow.log_param("target_column", TARGET_COLUMN)
        mlflow.log_param("feature_columns", json.dumps(FEATURE_COLUMNS))
        mlflow.log_param("test_days", TEST_DAYS)
        mlflow.log_param("split_cutoff", str(cutoff.date()))
        mlflow.log_param("train_rows", len(train_df))
        mlflow.log_param("test_rows", len(test_df))

        model = xgb.XGBRegressor(**model_params)
        model.fit(x_train, y_train, eval_set=[(x_test, y_test)], verbose=False)

        train_predictions = model.predict(x_train)
        test_predictions = model.predict(x_test)
        metrics = {
            **_regression_metrics(y_train, train_predictions, "train"),
            **_regression_metrics(y_test, test_predictions, "test"),
        }
        mlflow.log_metrics(metrics)
        if hasattr(model, "best_iteration"):
            mlflow.log_metric("best_iteration", float(model.best_iteration))

        model_info = mlflow.xgboost.log_model(model, artifact_path="model")
        model_version = mlflow.register_model(
            model_uri=model_info.model_uri,
            name=MLFLOW_REGISTERED_MODEL_NAME,
        )

        version_tags = {
            "role": "challenger",
            "run_id": run.info.run_id,
            "feature_columns": json.dumps(FEATURE_COLUMNS),
            **{name: str(value) for name, value in metrics.items()},
        }
        for key, value in version_tags.items():
            client.set_model_version_tag(
                MLFLOW_REGISTERED_MODEL_NAME,
                model_version.version,
                key,
                value,
            )

        challenger_pointer = f"{REGISTRY_DIR}/challenger_version.txt"
        write_text(challenger_pointer, str(model_version.version))

        print("\nMetrics:")
        for name, value in metrics.items():
            print(f"  {name}: {value:.4f}")
        print(
            f"\nRegistered {MLFLOW_REGISTERED_MODEL_NAME} version "
            f"{model_version.version} (challenger)"
        )
        print(f"Challenger version pointer: {challenger_pointer}")
        print(f"MLflow run ID: {run.info.run_id}")
        print(f"MLflow tracking URI: {MLFLOW_URI}")

    return metrics


if __name__ == "__main__":
    train()