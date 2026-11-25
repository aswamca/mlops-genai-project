"""Register the MLflow champion as a pending SageMaker model package."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path
from typing import Any

import boto3
import mlflow
import mlflow.xgboost
import xgboost as xgb
from botocore.exceptions import ClientError
from sagemaker import image_uris

from config import (
    AWS_REGION,
    MLFLOW_REGISTERED_MODEL_NAME,
    MLFLOW_URI,
    S3_BUCKET,
    S3_PREFIX,
    SAGEMAKER_MODEL_PACKAGE_GROUP,
    SAGEMAKER_XGBOOST_VERSION,
    banner,
)
from mlflow_registry import load_champion_model


def _ensure_package_group(client: Any) -> None:
    try:
        client.describe_model_package_group(
            ModelPackageGroupName=SAGEMAKER_MODEL_PACKAGE_GROUP
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "ResourceNotFound":
            raise
        client.create_model_package_group(
            ModelPackageGroupName=SAGEMAKER_MODEL_PACKAGE_GROUP,
            ModelPackageGroupDescription=(
                "Approved PredML cost-forecasting model versions mirrored "
                "from the MLflow champion."
            ),
            Tags=[{"Key": "Project", "Value": "PredML"}],
        )
        print(f"Created SageMaker model package group: {SAGEMAKER_MODEL_PACKAGE_GROUP}")


def _find_registered_champion(client: Any, mlflow_version: str) -> str | None:
    paginator = client.get_paginator("list_model_packages")
    for page in paginator.paginate(
        ModelPackageGroupName=SAGEMAKER_MODEL_PACKAGE_GROUP,
        SortBy="CreationTime",
        SortOrder="Descending",
    ):
        for package in page.get("ModelPackageSummaryList", []):
            details = client.describe_model_package(
                ModelPackageName=package["ModelPackageArn"]
            )
            metadata = details.get("CustomerMetadataProperties", {})
            if (
                metadata.get("mlflow_model_name") == MLFLOW_REGISTERED_MODEL_NAME
                and metadata.get("mlflow_model_version") == mlflow_version
            ):
                return package["ModelPackageArn"]
    return None


def _create_model_archive(mlflow_version: str, archive_path: Path) -> None:
    model_uri = f"models:/{MLFLOW_REGISTERED_MODEL_NAME}/{mlflow_version}"
    model = mlflow.xgboost.load_model(model_uri)
    model_file = archive_path.parent / "xgboost-model"
    booster = model if isinstance(model, xgb.Booster) else model.get_booster()
    booster.save_model(str(model_file))
    with tarfile.open(archive_path, mode="w:gz") as archive:
        archive.add(model_file, arcname="xgboost-model")


def _upload_model_archive(mlflow_version: str) -> str:
    model_key = "/".join(
        part
        for part in (
            S3_PREFIX,
            "model-registry",
            MLFLOW_REGISTERED_MODEL_NAME,
            f"mlflow-version-{mlflow_version}",
            "model.tar.gz",
        )
        if part
    )
    model_uri = f"s3://{S3_BUCKET}/{model_key}"
    s3 = boto3.client("s3", region_name=AWS_REGION)
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / "model.tar.gz"
        _create_model_archive(mlflow_version, archive_path)
        s3.upload_file(str(archive_path), S3_BUCKET, model_key)
    return model_uri


def register_champion() -> str:
    banner("STAGE 11 - SAGEMAKER MODEL REGISTRY")
    mlflow.set_tracking_uri(MLFLOW_URI)

    champion = load_champion_model()
    mlflow_version = str(champion.version)
    role = (champion.tags or {}).get("role")
    if role != "champion":
        raise RuntimeError(
            f"MLflow version {mlflow_version} has role {role!r}, not 'champion'. "
            "Only the MLflow champion can be copied to SageMaker Model Registry."
        )

    client = boto3.client("sagemaker", region_name=AWS_REGION)
    _ensure_package_group(client)
    existing_package = _find_registered_champion(client, mlflow_version)
    if existing_package:
        print(
            f"MLflow champion {MLFLOW_REGISTERED_MODEL_NAME} v{mlflow_version} "
            f"is already registered: {existing_package}"
        )
        return existing_package

    image_uri = image_uris.retrieve(
        framework="xgboost",
        region=AWS_REGION,
        version=SAGEMAKER_XGBOOST_VERSION,
        py_version="py3",
        instance_type="ml.m5.large",
    )
    feature_columns = (champion.tags or {}).get("feature_columns")
    if not feature_columns:
        raise RuntimeError(
            f"MLflow champion {MLFLOW_REGISTERED_MODEL_NAME} v{mlflow_version} "
            "has no feature_columns tag."
        )
    model_data_url = _upload_model_archive(mlflow_version)
    metrics = {
        key: str(value)
        for key, value in (champion.tags or {}).items()
        if key in {"test_mape", "test_rmse", "test_r2"}
    }
    metadata = {
        "mlflow_model_name": MLFLOW_REGISTERED_MODEL_NAME,
        "mlflow_model_version": mlflow_version,
        "mlflow_run_id": (champion.tags or {}).get("run_id", "unknown"),
        "approval_source": "mlflow_champion",
        "feature_columns": feature_columns,
        **metrics,
    }
    response = client.create_model_package(
        ModelPackageGroupName=SAGEMAKER_MODEL_PACKAGE_GROUP,
        ModelPackageDescription=(
            f"PredML champion {MLFLOW_REGISTERED_MODEL_NAME} v{mlflow_version}; "
            "pending manual approval before deployment."
        ),
        ModelApprovalStatus="PendingManualApproval",
        InferenceSpecification={
            "Containers": [
                {
                    "Image": image_uri,
                    "ModelDataUrl": model_data_url,
                }
            ],
            "SupportedContentTypes": ["text/csv"],
            "SupportedResponseMIMETypes": ["text/csv"],
            "SupportedRealtimeInferenceInstanceTypes": ["ml.m5.large"],
            "SupportedTransformInstanceTypes": ["ml.m5.large"],
        },
        CustomerMetadataProperties=metadata,
    )
    package_arn = response["ModelPackageArn"]
    print(
        f"Registered MLflow champion {MLFLOW_REGISTERED_MODEL_NAME} "
        f"v{mlflow_version} in SageMaker Model Registry."
    )
    print(f"Model package group: {SAGEMAKER_MODEL_PACKAGE_GROUP}")
    print(f"Model package ARN: {package_arn}")
    print("Approval status: PendingManualApproval")
    print("No endpoint was created.")
    return package_arn


if __name__ == "__main__":
    register_champion()
