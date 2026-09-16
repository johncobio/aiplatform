variable "name" {
  description = "Workload name; used for the instance, role and security group"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  description = "Public subnet to launch into"
  type        = string
}

variable "instance_type" {
  description = "Graviton (arm64) instance type; images are built for linux/arm64"
  type        = string
  default     = "t4g.small"

  validation {
    condition     = can(regex("^(t4g|c7g|m7g|c6g|m6g)\\.", var.instance_type))
    error_message = "Use an arm64 (Graviton) instance type; the image is built for linux/arm64."
  }
}

variable "image" {
  description = "Full image reference to run, e.g. <account>.dkr.ecr.<region>.amazonaws.com/aiplatform/llm-service:<tag>"
  type        = string
}

variable "ecr_repository_arn" {
  description = "Repository the instance may pull from (least privilege)"
  type        = string
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "allowed_cidrs" {
  description = "CIDRs allowed to reach the container port. Keep this to your own IP."
  type        = list(string)

  validation {
    condition     = !contains(var.allowed_cidrs, "0.0.0.0/0")
    error_message = "Refusing to expose the service to the whole internet; restrict allowed_cidrs to your IP."
  }
}

variable "container_env" {
  description = "Environment variables passed to the container"
  type        = map(string)
  default     = {}
}

variable "container_memory_mb" {
  description = "Docker memory limit for the container"
  type        = number
  default     = 1536
}

variable "root_volume_gb" {
  type    = number
  default = 20
}

variable "tags" {
  type    = map(string)
  default = {}
}
