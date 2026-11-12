output "portal_url" {
  description = "HTTPS landing page. Guests also need an invite fragment."
  value       = aws_apigatewayv2_api.portal.api_endpoint
}

output "function_name" {
  description = "IAM-authorized operator function."
  value       = aws_lambda_function.portal.function_name
}
