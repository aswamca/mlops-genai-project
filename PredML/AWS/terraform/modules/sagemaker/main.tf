resource "aws_sagemaker_mlflow_tracking_server" "predml" {
  tracking_server_name = var.mlflow_server_name
  artifact_store_uri   = "s3://${var.s3_bucket}/mlflow-artifacts/"
  role_arn             = var.execution_role_arn
  tracking_server_size = "Small"

  tags = {
    Project = var.project
  }
}

resource "aws_sagemaker_feature_group" "predml" {
  feature_group_name             = var.feature_group_name
  record_identifier_feature_name = "record_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.execution_role_arn

  feature_definition {
    feature_name = "record_id"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "event_time"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "feature_1"
    feature_type = "Fractional"
  }

  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.s3_bucket}/features/"
    }
  }

  tags = {
    Project = var.project
  }
}
