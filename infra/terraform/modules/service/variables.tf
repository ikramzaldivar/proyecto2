variable "name_prefix" {
  description = "Prefix shared by every resource name, as <project>-<environment>."
  type        = string
}

variable "aws_region" {
  description = "AWS region, used by the awslogs driver."
  type        = string
}

variable "vpc_id" {
  description = "VPC where the target groups live."
  type        = string
}

variable "public_subnet_ids" {
  description = "Subnets used by the load balancer and the Fargate tasks."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group of the public load balancer."
  type        = string
}

variable "frontend_security_group_id" {
  description = "Security group of the frontend tasks."
  type        = string
}

variable "backend_security_group_id" {
  description = "Security group of the backend tasks."
  type        = string
}

variable "ecr_repository_urls" {
  description = "Map with the frontend and backend ECR repository URLs."
  type        = map(string)

  validation {
    condition     = alltrue([for name in ["frontend", "backend"] : contains(keys(var.ecr_repository_urls), name)])
    error_message = "ecr_repository_urls must contain both frontend and backend keys."
  }
}

variable "container_image_tag" {
  description = "Immutable Git commit tag shared by the frontend and backend images."
  type        = string

  validation {
    condition     = length(trimspace(var.container_image_tag)) > 0 && var.container_image_tag != "latest"
    error_message = "container_image_tag must be a non-empty immutable tag, not latest."
  }
}

variable "service_desired_count" {
  description = "Desired task count for each ECS service."
  type        = number
  default     = 1

  validation {
    condition     = var.service_desired_count >= 1
    error_message = "service_desired_count must be at least 1."
  }
}

variable "log_retention_days" {
  description = "CloudWatch log retention for application containers."
  type        = number
  default     = 7
}

variable "db_host" {
  description = "Hostname of the MariaDB instance."
  type        = string
}

variable "db_port" {
  description = "Port of the MariaDB instance."
  type        = number
}

variable "db_name" {
  description = "Database the backend connects to."
  type        = string
}

variable "db_username" {
  description = "MariaDB administrator username."
  type        = string
}

variable "db_secret_arn" {
  description = "Secrets Manager ARN with the password generated and rotated by RDS."
  type        = string
}

variable "app_images_bucket" {
  description = "Name of the S3 bucket where the portal stores the images."
  type        = string
}

variable "app_images_bucket_arn" {
  description = "ARN of that same bucket, used to scope the backend task policy."
  type        = string
}
