module "s3" {
  source      = "./modules/s3"
  bucket_name = var.s3_bucket_name
  project     = var.project_name
}

module "ecr" {
  source     = "./modules/ecr"
  batch_repo = var.ecr_batch_repo
  api_repo   = var.ecr_api_repo
  project    = var.project_name
}

module "iam" {
  source    = "./modules/iam"
  role_name = var.sagemaker_role_name
  project   = var.project_name
}

module "sagemaker" {
  source             = "./modules/sagemaker"
  execution_role_arn = module.iam.sagemaker_role_arn
  s3_bucket          = module.s3.bucket_name
  mlflow_server_name = var.mlflow_server_name
  feature_group_name = var.feature_group_name
  project            = var.project_name
}

module "eventbridge" {
  source                   = "./modules/eventbridge"
  sagemaker_role_arn       = module.iam.eventbridge_role_arn
  project                  = var.project_name
  aws_region               = var.aws_region
  aws_account_id           = data.aws_caller_identity.current.account_id
  batch_pipeline_name      = var.batch_pipeline_name
  monitoring_pipeline_name = var.monitoring_pipeline_name
}
