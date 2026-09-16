provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name = "${var.project}-${var.environment}"
}

module "network" {
  source = "../../modules/network"

  name = local.name
  cidr = "10.20.0.0/16"
  public_subnet_cidrs = [
    "10.20.0.0/20",
    "10.20.16.0/20",
  ]
}

module "ecr" {
  source = "../../modules/ecr"

  name = "${var.project}/${var.workload_name}"
}

module "service" {
  source = "../../modules/ec2-service"
  count  = var.enable_compute ? 1 : 0

  name               = "${local.name}-${var.workload_name}"
  vpc_id             = module.network.vpc_id
  subnet_id          = module.network.public_subnet_ids[0]
  instance_type      = var.instance_type
  image              = "${module.ecr.repository_url}:${var.image_tag}"
  ecr_repository_arn = module.ecr.repository_arn
  allowed_cidrs      = var.allowed_cidrs
  container_env      = var.container_env

}
