resource "aws_apigatewayv2_api" "application" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"

  tags = {
    Component = "api-gateway"
  }
}

resource "aws_apigatewayv2_integration" "alb" {
  api_id = aws_apigatewayv2_api.application.id

  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${aws_lb.application.dns_name}"

  connection_type        = "INTERNET"
  payload_format_version = "1.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "default" {
  api_id = aws_apigatewayv2_api.application.id

  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name_prefix}"
  retention_in_days = var.cloudwatch_log_retention_days
  kms_key_id        = var.cloudwatch_log_kms_key_arn

  tags = {
    Component = "api-gateway"
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.application.id

  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      routeKey         = "$context.routeKey"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
      sourceIp         = "$context.identity.sourceIp"
    })
  }

  tags = {
    Component = "api-gateway"
  }
}
