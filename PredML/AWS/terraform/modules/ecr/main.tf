resource "aws_ecr_repository" "batch" {
  name                 = var.batch_repo
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project = var.project
  }
}

resource "aws_ecr_repository" "api" {
  name                 = var.api_repo
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project = var.project
  }
}
