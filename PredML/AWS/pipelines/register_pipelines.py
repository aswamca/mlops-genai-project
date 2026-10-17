"""Create or update the PredML SageMaker pipeline definitions.

The pipeline steps run the stages from the batch ECR image. Model tracking and
registration are performed by the SageMaker MLflow Tracking Server.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import boto3
from botocore.exceptions import ClientError


def _processing_step(
    name: str,
    stage: str,
    image_uri: str,
    role_arn: str,
    bucket: str,
    tracking_uri: str,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "Name": name,
        "Type": "Processing",
        "Arguments": {
            "ProcessingResources": {
                "ClusterConfig": {
                    "InstanceType": "ml.t3.medium",
                    "InstanceCount": 1,
                    "VolumeSizeInGB": 30,
                }
            },
            "AppSpecification": {
                "ImageUri": image_uri,
            },
            "Environment": {
                "AWS_DEFAULT_REGION": "",
                "AWS_REGION": "",
                "S3_BUCKET": bucket,
                "STAGE": stage,
                "MLFLOW_TRACKING_URI": tracking_uri,
            },
            "RoleArn": role_arn,
        },
    }
    if depends_on:
        step["DependsOn"] = depends_on
    return step


def _pipeline_definition(
    stages: list[tuple[str, str]],
    image_uri: str,
    role_arn: str,
    bucket: str,
    region: str,
    tracking_uri: str,
) -> str:
    steps: list[dict[str, Any]] = []
    previous: list[str] = []
    for name, stage in stages:
        steps.append(
            _processing_step(
                name,
                stage,
                image_uri,
                role_arn,
                bucket,
                tracking_uri,
                previous or None,
            )
        )
        previous = [name]

    for step in steps:
        environment = step["Arguments"]["Environment"]
        environment["AWS_DEFAULT_REGION"] = region
        environment["AWS_REGION"] = region
    return json.dumps({"Version": "2020-12-01", "Steps": steps})


def _upsert(
    client: Any,
    name: str,
    definition: str,
    role_arn: str,
) -> None:
    try:
        client.describe_pipeline(PipelineName=name)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code != "ResourceNotFound":
            raise
        client.create_pipeline(
            PipelineName=name,
            PipelineDefinition=definition,
            RoleArn=role_arn,
            PipelineDescription=f"PredML {name} pipeline",
        )
        print(f"Created SageMaker pipeline: {name}")
        return

    client.update_pipeline(
        PipelineName=name,
        PipelineDefinition=definition,
        RoleArn=role_arn,
        PipelineDescription=f"PredML {name} pipeline",
    )
    print(f"Updated SageMaker pipeline: {name}")


def register_pipelines(
    region: str,
    bucket: str,
    image_uri: str,
    role_arn: str,
    tracking_uri: str,
    training_name: str,
    batch_name: str,
    monitoring_name: str,
    rollback_name: str,
) -> None:
    client = boto3.client("sagemaker", region_name=region)
    if ":" not in image_uri.rsplit("/", 1)[-1]:
        image_uri = f"{image_uri}:latest"
    definitions = {
        training_name: [
            ("Preprocess", "01_preprocess"),
            ("FeatureEngineering", "02_feature_engineering"),
            ("FeatureStore", "03_feature_store"),
            ("TrainModel", "04_train_model"),
            ("RegisterModel", "05_register_model"),
        ],
        batch_name: [("BatchInference", "06_batch_inference")],
        monitoring_name: [("ModelMonitoring", "08_model_monitoring")],
        rollback_name: [("Rollback", "10_rollback")],
    }
    for name, stages in definitions.items():
        _upsert(
            client,
            name,
            _pipeline_definition(
                stages, image_uri, role_arn, bucket, region, tracking_uri
            ),
            role_arn,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--image-uri", required=True)
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--training-name", default="PredML-Training-Pipeline")
    parser.add_argument("--batch-name", default="PredML-Batch-Inference-Pipeline")
    parser.add_argument(
        "--monitoring-name", default="PredML-Monitoring-Pipeline"
    )
    parser.add_argument("--rollback-name", default="PredML-Rollback-Pipeline")
    args = parser.parse_args()
    register_pipelines(
        region=args.region,
        bucket=args.bucket,
        image_uri=args.image_uri,
        role_arn=args.role_arn,
        tracking_uri=args.tracking_uri,
        training_name=args.training_name,
        batch_name=args.batch_name,
        monitoring_name=args.monitoring_name,
        rollback_name=args.rollback_name,
    )


if __name__ == "__main__":
    main()
