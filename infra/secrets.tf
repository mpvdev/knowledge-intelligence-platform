resource "aws_secretsmanager_secret" "application" {
  name        = local.application_secret
  description = "Application secrets for the Knowledge Intelligence service."

  recovery_window_in_days = var.secret_recovery_window_in_days

  tags = {
    Component = "application-secrets"
  }
}
