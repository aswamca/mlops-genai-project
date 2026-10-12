resource "aws_scheduler_schedule" "batch_inference" {
  name = "${var.project}-batch-inference-schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.batch_schedule_expression

  target {
    arn      = "arn:aws:sagemaker:${var.aws_region}:${var.aws_account_id}:pipeline/${var.batch_pipeline_name}"
    role_arn = var.sagemaker_role_arn

    sagemaker_pipeline_parameters {
    }
  }
}

resource "aws_scheduler_schedule" "monitoring" {
  name = "${var.project}-monitoring-schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.monitoring_schedule_expression

  target {
    arn      = "arn:aws:sagemaker:${var.aws_region}:${var.aws_account_id}:pipeline/${var.monitoring_pipeline_name}"
    role_arn = var.sagemaker_role_arn

    sagemaker_pipeline_parameters {
    }
  }
}
