# PredML Terraform

This directory is the Terraform root module for the AWS resources described in
[`Setup.txt`](./Setup.txt). The reusable modules are kept under `modules/`:

- `s3`: encrypted, versioned data and artifact bucket
- `ecr`: batch and API container repositories
- `iam`: SageMaker and EventBridge Scheduler roles
- `sagemaker`: MLflow tracking server and Feature Store group
- `eventbridge`: batch inference and monitoring schedules

## Usage

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and set a globally
   unique S3 bucket name.
2. Ensure the remote state bucket
   `predml-terraform-state-ap-southeast-2` already exists.
3. Run `terraform init`, `terraform validate`, and `terraform plan`.
4. Apply only after reviewing the plan:

```powershell
terraform init
terraform validate
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

The remote state bucket must be bootstrapped separately because Terraform
cannot use a backend resource before that resource exists. Do not commit
`terraform.tfvars` or state files.
