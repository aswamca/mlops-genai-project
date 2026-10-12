variable "aws_region" {
  description = "AWS region where the PredML infrastructure is provisioned."
  type        = string
  default     = "ap-southeast-2"
}

variable "project_name" {
  description = "Project name used in resource names and tags."
  type        = string
  default     = "predml"
}

variable "s3_bucket_name" {
  description = "Globally unique S3 bucket name for PredML data and artifacts."
  type        = string
}

variable "ecr_batch_repo" {
  description = "ECR repository name for the batch inference image."
  type        = string
  default     = "predml-batch"
}

variable "ecr_api_repo" {
  description = "ECR repository name for the real-time API image."
  type        = string
  default     = "predml-api"
}

variable "sagemaker_role_name" {
  description = "Name of the SageMaker execution IAM role."
  type        = string
  default     = "PredML-SageMaker-ExecutionRole"
}

variable "mlflow_server_name" {
  description = "SageMaker MLflow tracking server name."
  type        = string
  default     = "predml-mlflow-tracker"
}

variable "feature_group_name" {
  description = "SageMaker Feature Store feature group name."
  type        = string
  default     = "predml-feature-group"
}

variable "batch_pipeline_name" {
  description = "SageMaker pipeline started by the batch schedule."
  type        = string
  default     = "PredML-Batch-Inference-Pipeline"
}

variable "monitoring_pipeline_name" {
  description = "SageMaker pipeline started by the monitoring schedule."
  type        = string
  default     = "PredML-Monitoring-Pipeline"
}
