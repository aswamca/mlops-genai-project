output "s3_bucket_name" {
  description = "PredML data bucket name."
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "PredML data bucket ARN."
  value       = module.s3.bucket_arn
}

output "ecr_batch_uri" {
  description = "Batch inference ECR repository URI."
  value       = module.ecr.batch_repo_uri
}

output "ecr_api_uri" {
  description = "API ECR repository URI."
  value       = module.ecr.api_repo_uri
}

output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN."
  value       = module.iam.sagemaker_role_arn
}

output "eventbridge_role_arn" {
  description = "EventBridge Scheduler execution role ARN."
  value       = module.iam.eventbridge_role_arn
}

output "mlflow_tracking_uri" {
  description = "SageMaker MLflow tracking server URI."
  value       = module.sagemaker.mlflow_tracking_uri
}

output "mlflow_tracking_server_arn" {
  description = "SageMaker MLflow tracking server ARN used by the AWS MLflow plugin."
  value       = "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:mlflow-tracking-server/${var.mlflow_server_name}"
}

output "feature_group_name" {
  description = "SageMaker Feature Store feature group name."
  value       = module.sagemaker.feature_group_name
}
