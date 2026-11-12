locals {
  name = "aiplatform-remote-preview"
  app  = "${path.module}/../../../../services/preview-demo/remote_portal"
}

data "archive_file" "portal" {
  type        = "zip"
  output_path = "${path.module}/.terraform/portal.zip"

  dynamic "source" {
    for_each = toset(["__init__.py", "handler.py", "demo_form.py", "index.html", "app.js"])
    content {
      content  = file("${local.app}/${source.value}")
      filename = "remote_portal/${source.value}"
    }
  }
}

resource "aws_dynamodb_table" "requests" {
  #checkov:skip=CKV_AWS_28:ADR 0015. Ephemeral demo invitations are intentionally not recoverable after cleanup.
  #checkov:skip=CKV_AWS_119:ADR 0015. DynamoDB encryption is on; this low-volume demo uses the AWS-managed key.
  name         = local.name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "key"

  attribute {
    name = "key"
    type = "S"
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  server_side_encryption {
    enabled = true
  }
  on_demand_throughput {
    max_read_request_units  = 10
    max_write_request_units = 5
  }
}

resource "aws_lambda_function" "portal" {
  #checkov:skip=CKV_AWS_117:ADR 0015. Managed AWS APIs only; no VPC, NAT or private service dependencies.
  #checkov:skip=CKV_AWS_116:ADR 0015. Both entry points are synchronous; errors are returned to the caller.
  #checkov:skip=CKV_AWS_173:ADR 0015. The only environment value is a non-secret table name.
  #checkov:skip=CKV_AWS_272:ADR 0015. The reviewed Terraform plan pins the zip by SHA256; no separate signing stack.
  #checkov:skip=CKV_AWS_50:ADR 0015. Short-lived access and execution logs cover the demo; no tracing stack.
  function_name                  = local.name
  role                           = aws_iam_role.portal.arn
  handler                        = "remote_portal.handler.lambda_handler"
  runtime                        = "python3.12"
  filename                       = data.archive_file.portal.output_path
  source_code_hash               = data.archive_file.portal.output_base64sha256
  timeout                        = 10
  memory_size                    = 128
  reserved_concurrent_executions = 5

  environment {
    variables = { REQUEST_TABLE = aws_dynamodb_table.requests.name }
  }
  depends_on = [aws_iam_role_policy.portal, aws_cloudwatch_log_group.function]
}

resource "aws_apigatewayv2_api" "portal" {
  name            = local.name
  protocol_type   = "HTTP"
  ip_address_type = "ipv4"
}

resource "aws_apigatewayv2_integration" "portal" {
  api_id                 = aws_apigatewayv2_api.portal.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.portal.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "portal" {
  #checkov:skip=CKV_AWS_309:ADR 0015. Invite bearer authentication is enforced inside Lambda; operator invokes through IAM only.
  api_id    = aws_apigatewayv2_api.portal.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.portal.id}"
}

resource "aws_apigatewayv2_stage" "portal" {
  api_id      = aws_apigatewayv2_api.portal.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId  = "$context.requestId"
      status     = "$context.status"
      latency    = "$context.responseLatency"
      httpMethod = "$context.httpMethod"
    })
  }
}

resource "aws_lambda_permission" "gateway" {
  statement_id  = "AllowOnlyPortalApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.portal.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.portal.execution_arn}/*"
}
