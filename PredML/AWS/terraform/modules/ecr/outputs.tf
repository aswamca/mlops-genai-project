output "batch_repo_uri" {
  description = "Batch inference repository URI."
  value       = aws_ecr_repository.batch.repository_url
}

output "api_repo_uri" {
  description = "API repository URI."
  value       = aws_ecr_repository.api.repository_url
}
