output "mlflow_tracking_uri" {
  description = "SageMaker MLflow tracking server URI."
  value       = aws_sagemaker_mlflow_tracking_server.predml.tracking_server_url
}

output "feature_group_name" {
  description = "SageMaker Feature Store feature group name."
  value       = aws_sagemaker_feature_group.predml.feature_group_name
}
