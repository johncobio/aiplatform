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

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
