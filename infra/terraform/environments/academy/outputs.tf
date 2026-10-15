output "endpoint" {
  description = "Temporary plaintext demo endpoint, reachable only from operator_cidr"
  value       = "http://${aws_instance.academy_demo.public_ip}:8000"
}

output "instance_id" {
  value = aws_instance.academy_demo.id
}
