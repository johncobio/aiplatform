variable "operator_cidr" {
  description = "Operator's current public IPv4 /32; no world-open or shared-network access"
  type        = string
  validation {
    condition = (
      can(cidrnetmask(var.operator_cidr)) &&
      endswith(var.operator_cidr, "/32") &&
      !contains(["0.0.0.0/32", "127.0.0.1/32"], var.operator_cidr)
    )
    error_message = "Use your current public IPv4 address followed by /32."
  }
}
