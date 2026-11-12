resource "aws_cloudwatch_log_group" "function" {
  #checkov:skip=CKV_AWS_158:ADR 0015. No customer-managed key for short-lived, non-sensitive demo logs.
  #checkov:skip=CKV_AWS_338:ADR 0015. Keep only seven days of minimal demo logs.
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "access" {
  #checkov:skip=CKV_AWS_158:ADR 0015. No customer-managed key for short-lived, non-sensitive demo logs.
  #checkov:skip=CKV_AWS_338:ADR 0015. Keep only seven days of minimal demo logs.
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 7
}

resource "aws_iam_role" "portal" {
  name = local.name
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "portal" {
  name = "portal-data-and-logs"
  role = aws_iam_role.portal.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem"]
        Resource = aws_dynamodb_table.requests.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.function.arn}:*"
      }
    ]
  })
}
