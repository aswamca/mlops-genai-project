output "batch_schedule_arn" {
  description = "Batch inference schedule ARN."
  value       = aws_scheduler_schedule.batch_inference.arn
}

output "monitoring_schedule_arn" {
  description = "Monitoring schedule ARN."
  value       = aws_scheduler_schedule.monitoring.arn
}
