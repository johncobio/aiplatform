output "preview" {
  description = "Temporary HTTP endpoint. Use synthetic inputs only."
  value = {
    endpoint    = "http://${aws_instance.academy_demo.public_ip}:8000"
    instance_id = aws_instance.academy_demo.id
    version     = var.preview_version
    minutes     = var.preview_minutes
  }
}
