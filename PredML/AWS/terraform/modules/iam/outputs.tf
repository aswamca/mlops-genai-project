output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN."
  value       = aws_iam_role.sagemaker_execution.arn
}

output "eventbridge_role_arn" {
  description = "EventBridge Scheduler role ARN."
  value       = aws_iam_role.eventbridge_sagemaker.arn
}
