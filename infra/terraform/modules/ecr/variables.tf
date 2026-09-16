variable "name" {
  description = "Repository name, e.g. aiplatform/llm-service"
  type        = string
}

variable "keep_last_images" {
  description = "How many tagged images the lifecycle policy retains"
  type        = number
  default     = 10
}

variable "tags" {
  type    = map(string)
  default = {}
}
