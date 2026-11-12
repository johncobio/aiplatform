terraform {
  required_version = ">= 1.10"
}

variable "preview_version" {
  type = number
  validation {
    condition     = contains([1, 2], var.preview_version)
    error_message = "Use version 1 or 2."
  }
}

variable "preview_minutes" {
  type = number
  validation {
    condition     = contains([15, 30], var.preview_minutes)
    error_message = "Use a lifetime of 15 or 30 minutes."
  }
}

resource "terraform_data" "preview" {
  input = {
    version = var.preview_version
    minutes = var.preview_minutes
  }
}

output "preview" {
  value = terraform_data.preview.output
}
