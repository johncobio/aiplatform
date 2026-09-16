variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "aiplatform"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "workload_name" {
  description = "Workload served by this environment (matches aiplatform.yaml name)"
  type        = string
  default     = "llm-service"
}

variable "enable_compute" {
  description = "Create the EC2 host. Leave false until an image has been pushed to ECR."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Image tag in ECR to run (required when enable_compute = true)"
  type        = string
  default     = ""

  validation {
    condition     = !var.enable_compute || var.image_tag != ""
    error_message = "image_tag must be set when enable_compute = true."
  }
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "allowed_cidrs" {
  description = "Your public IP as /32, e.g. [\"203.0.113.10/32\"]"
  type        = list(string)
  default     = []

  validation {
    condition     = !var.enable_compute || length(var.allowed_cidrs) > 0
    error_message = "allowed_cidrs must contain at least your own /32 when enable_compute = true."
  }
}

variable "container_env" {
  type = map(string)
  default = {
    LLM_MODEL_NAME     = "qwen2.5-0.5b-instruct"
    LLM_MODEL_URL      = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LLM_CONTEXT_LENGTH = "2048"
    LLM_THREADS        = "2"
  }
}
