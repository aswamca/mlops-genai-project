output "bucket_name" {
  description = "Created S3 bucket name."
  value       = aws_s3_bucket.data.bucket
}

output "bucket_arn" {
  description = "Created S3 bucket ARN."
  value       = aws_s3_bucket.data.arn
}
