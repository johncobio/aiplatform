output "vpc_id" {
  value = module.network.vpc_id
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "endpoint" {
  value = var.enable_compute ? module.service[0].endpoint : null
}

output "instance_id" {
  value = var.enable_compute ? module.service[0].instance_id : null
}
