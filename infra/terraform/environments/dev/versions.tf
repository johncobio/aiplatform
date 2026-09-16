terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Partial backend configuration: bucket/key/region come from backend.hcl
  # (gitignored; see backend.example.hcl) via `terraform init -backend-config=backend.hcl`.
  backend "s3" {
    use_lockfile = true
    encrypt      = true
  }
}
