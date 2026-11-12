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

variable "operator_cidr" {
  description = "Current public IPv4 /32 of the demo operator."
  type        = string
  validation {
    condition = (
      can(cidrnetmask(var.operator_cidr)) &&
      endswith(var.operator_cidr, "/32") &&
      try(tonumber(split(".", var.operator_cidr)[0]) < 224, false) &&
      !contains(["0.0.0.0/32", "127.0.0.1/32"], var.operator_cidr)
    )
    error_message = "Use your current public IPv4 address followed by /32."
  }
}

variable "expected_account_id" {
  description = "AWS account selected by the operator for this workspace."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "Use the 12-digit account returned by STS for this lab session."
  }
}
