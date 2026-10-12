variable "execution_role_arn" {
  description = "IAM role assumed by SageMaker."
  type        = string
}

variable "s3_bucket" {
  description = "S3 bucket name used for MLflow and Feature Store artifacts."
  type        = string
}

variable "mlflow_server_name" {
  description = "SageMaker MLflow tracking server name."
  type        = string
}

variable "feature_group_name" {
  description = "SageMaker Feature Store feature group name."
  type        = string
}

variable "project" {
  description = "Project tag value."
  type        = string
}
