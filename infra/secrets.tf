data "aws_secretsmanager_secret" "application" {
  name = local.application_secret
}
