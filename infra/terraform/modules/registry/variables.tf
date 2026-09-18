variable "name_prefix" {
  description = "Prefix shared by every resource name, as <project>-<environment>."
  type        = string
}

variable "image_retention_count" {
  description = "Maximum number of images retained in each ECR repository."
  type        = number
  default     = 10

  validation {
    condition     = var.image_retention_count >= 1
    error_message = "image_retention_count must be at least 1."
  }
}
