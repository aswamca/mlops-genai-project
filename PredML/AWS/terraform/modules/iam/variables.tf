variable "role_name" {
  description = "Name of the SageMaker execution role."
  type        = string
}

variable "project" {
  description = "Project tag and naming value."
  type        = string
}

variable "aws_region" {
  description = "AWS region containing the MLflow tracking server."
  type        = string
}

variable "aws_account_id" {
  description = "AWS account containing the MLflow tracking server."
  type        = string
}

variable "mlflow_server_name" {
  description = "SageMaker MLflow tracking server name."
  type        = string
}
