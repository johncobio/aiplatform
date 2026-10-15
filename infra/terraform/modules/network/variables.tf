variable "name" {
  description = "Name prefix for all network resources"
  type        = string
}

variable "cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "One CIDR per public subnet; each is placed in a different AZ"
  type        = list(string)
  default     = ["10.0.0.0/20", "10.0.16.0/20"]

  validation {
    condition     = length(var.public_subnet_cidrs) >= 2
    error_message = "At least two public subnets are required (load balancers and EKS need two AZs)."
  }
}

variable "availability_zone_names" {
  description = "Explicit zone allowlist, in the same region as the provider; prevents discovery drift"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(distinct(var.availability_zone_names)) >= length(var.public_subnet_cidrs)
    error_message = "Provide one distinct allowed availability zone per public subnet."
  }
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
