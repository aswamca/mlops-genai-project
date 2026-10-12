variable "project" {
  description = "Project name used in schedule names."
  type        = string
}

variable "aws_region" {
  description = "AWS region containing the SageMaker pipelines."
  type        = string
}

variable "aws_account_id" {
  description = "AWS account containing the SageMaker pipelines."
  type        = string
}

variable "sagemaker_role_arn" {
  description = "IAM role assumed by EventBridge Scheduler."
  type        = string
}

variable "batch_pipeline_name" {
  description = "SageMaker pipeline for the batch inference schedule."
  type        = string
}

variable "monitoring_pipeline_name" {
  description = "SageMaker pipeline for the monitoring schedule."
  type        = string
}

variable "batch_schedule_expression" {
  description = "EventBridge schedule expression for batch inference."
  type        = string
  default     = "cron(0 2 * * ? *)"
}

variable "monitoring_schedule_expression" {
  description = "EventBridge schedule expression for monitoring."
  type        = string
  default     = "cron(0 4 * * ? *)"
}
