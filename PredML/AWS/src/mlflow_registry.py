from __future__ import annotations

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from config import (
    CHAMPION_ALIAS,
    MLFLOW_REGISTERED_MODEL_NAME,
    MLFLOW_URI,
    PREVIOUS_ALIAS,
)


def _client() -> MlflowClient:
    """Return a configured MLflow client."""
    mlflow.set_tracking_uri(MLFLOW_URI)
    return MlflowClient(tracking_uri=MLFLOW_URI)


def _alias_missing(error: MlflowException) -> bool:
    """Return True when MLflow reports that the requested alias does not exist."""
    code = getattr(error, "error_code", None)
    message = str(error).lower()
    return (
        code in {"RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"}
        or "alias" in message and "not found" in message
    )


def load_champion_model():
    """Load the champion model version from the MLflow model registry."""
    client = _client()
    try:
        return client.get_model_version_by_alias(
            MLFLOW_REGISTERED_MODEL_NAME,
            CHAMPION_ALIAS,
        )
    except MlflowException as error:
        if _alias_missing(error):
            raise RuntimeError(
                f"NO @{CHAMPION_ALIAS} alias set on model '{MLFLOW_REGISTERED_MODEL_NAME}'. "
                f"Run stage 5 first (05_register_model.py). Original: {error}"
            ) from error
        raise


def get_version_metrics(version: str) -> dict[str, float]:
    """Fetch the model version metrics stored as tags."""
    client = _client()
    model_version = client.get_model_version(
        MLFLOW_REGISTERED_MODEL_NAME,
        str(version),
    )
    metrics: dict[str, float] = {}
    for name in (
        "train_mape",
        "test_mape",
        "train_rmse",
        "test_rmse",
        "train_r2",
        "test_r2",
    ):
        if name in model_version.tags:
            metrics[name] = float(model_version.tags[name])
    return metrics


def get_latest_challenger_version() -> str:
    """Return the newest registered challenger version from MLflow."""
    client = _client()
    versions = client.search_model_versions(
        f"name='{MLFLOW_REGISTERED_MODEL_NAME}'"
    )
    challengers = [
        version
        for version in versions
        if version.tags.get("role") == "challenger"
    ]
    if not challengers:
        raise RuntimeError(
            f"No challenger version found for '{MLFLOW_REGISTERED_MODEL_NAME}'. "
            "Run the training stage first."
        )
    return str(max(challengers, key=lambda version: int(version.version)).version)


def get_champion_version() -> str | None:
    """Return the version currently assigned to the champion alias."""
    client = _client()
    try:
        champion = client.get_model_version_by_alias(
            MLFLOW_REGISTERED_MODEL_NAME,
            CHAMPION_ALIAS,
        )
    except MlflowException as error:
        if _alias_missing(error):
            return None
        raise
    return str(champion.version)


def tag_version(version: str, tags: dict[str, object]) -> None:
    """Apply tags to a registered model version."""
    client = _client()
    for key, value in tags.items():
        client.set_model_version_tag(
            MLFLOW_REGISTERED_MODEL_NAME,
            str(version),
            key,
            str(value),
        )


def promote_to_champion(
    challenger_version: str,
    previous_version: str | None,
) -> None:
    """Promote a challenger version to champion and move the old champion to previous."""
    client = _client()
    if previous_version is not None:
        client.set_registered_model_alias(
            MLFLOW_REGISTERED_MODEL_NAME,
            PREVIOUS_ALIAS,
            str(previous_version),
        )
    client.set_registered_model_alias(
        MLFLOW_REGISTERED_MODEL_NAME,
        CHAMPION_ALIAS,
        str(challenger_version),
    )
