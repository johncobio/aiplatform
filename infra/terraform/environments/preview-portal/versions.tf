terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

variable "expected_account_id" {
  description = "AWS account ID obtained privately from STS for the intended project."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Use the 12-digit account ID returned by STS."
  }
}

provider "aws" {
  region              = "us-east-2"
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project     = "aiplatform"
      Environment = "remote-preview"
      ManagedBy   = "terraform"
    }
  }
}
