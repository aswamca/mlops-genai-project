resource "aws_iam_role" "sagemaker_execution" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
  }
}

resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy_attachment" "s3_full" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ecr_full" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
}

resource "aws_iam_role_policy" "sagemaker_mlflow" {
  role = aws_iam_role.sagemaker_execution.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sagemaker-mlflow:*"
      Resource = "arn:aws:sagemaker:${var.aws_region}:${var.aws_account_id}:mlflow-tracking-server/${var.mlflow_server_name}"
    }]
  })
}

resource "aws_iam_role" "eventbridge_sagemaker" {
  name = "${var.project}-eventbridge-sagemaker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
  }
}

resource "aws_iam_role_policy" "eventbridge_sagemaker" {
  role = aws_iam_role.eventbridge_sagemaker.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sagemaker:StartPipelineExecution"
      Resource = "*"
    }]
  })
}
