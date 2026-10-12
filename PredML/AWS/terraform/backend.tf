terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "predml-terraform-state-ap-southeast-2"
    key     = "predml/terraform.tfstate"
    region  = "ap-southeast-2"
    encrypt = true
  }
}
