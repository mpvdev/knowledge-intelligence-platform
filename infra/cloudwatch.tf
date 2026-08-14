resource "aws_cloudwatch_log_group" "application" {
  name              = local.cloudwatch_log_name
  retention_in_days = var.cloudwatch_log_retention_days
  kms_key_id        = var.cloudwatch_log_kms_key_arn

  tags = {
    Component = "application-logging"
  }
}
