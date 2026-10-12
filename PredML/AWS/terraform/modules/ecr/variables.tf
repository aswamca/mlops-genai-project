variable "batch_repo" {
  description = "ECR repository name for batch inference."
  type        = string
}

variable "api_repo" {
  description = "ECR repository name for the API."
  type        = string
}

variable "project" {
  description = "Project tag value."
  type        = string
}
