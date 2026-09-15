variable "aws_region" {
  description = "AWS region used by the project."
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "proyecto2"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "prod"
}

variable "ecr_image_retention_count" {
  description = "Maximum number of images retained in each ECR repository."
  type        = number
  default     = 10

  validation {
    condition     = var.ecr_image_retention_count >= 1
    error_message = "ecr_image_retention_count must be at least 1."
  }
}

variable "release_retention_days" {
  description = "Governance Object Lock retention for dataset releases."
  type        = number
  default     = 1

  validation {
    condition     = var.release_retention_days >= 1
    error_message = "release_retention_days must be at least 1."
  }
}
