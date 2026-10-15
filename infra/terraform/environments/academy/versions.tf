terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Local state in the authenticated CloudShell home; never commit or upload it.
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Project     = "aiplatform"
      Environment = "academy"
      ManagedBy   = "terraform"
    }
  }
}
