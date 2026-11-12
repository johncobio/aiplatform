terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region              = "us-east-2"
  allowed_account_ids = [var.expected_account_id]
  default_tags {
    tags = {
      Project     = "aiplatform"
      Environment = "academy"
      ManagedBy   = "terraform"
    }
  }
}
