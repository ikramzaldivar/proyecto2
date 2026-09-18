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

variable "vpc_cidr" {
  description = "CIDR block of the VPC. PROD keeps the original range."
  type        = string
  default     = "10.20.0.0/16"
}

variable "ecr_image_retention_count" {
  description = "Maximum number of images retained in each ECR repository."
  type        = number
  default     = 10
}

variable "release_retention_days" {
  description = "Governance Object Lock retention for dataset releases."
  type        = number
  default     = 1
}

variable "container_image_tag" {
  description = "Immutable Git commit tag shared by the frontend and backend images."
  type        = string
}

variable "allowed_http_cidrs" {
  description = "CIDR ranges allowed to reach the public HTTP listener."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "db_name" {
  description = "Initial MariaDB database name."
  type        = string
  default     = "image_repo"
}

variable "db_username" {
  description = "MariaDB administrator username. The password is generated and managed by RDS."
  type        = string
  default     = "proyecto2_admin"
}

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "service_desired_count" {
  description = "Desired task count for each ECS service."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch log retention for application containers."
  type        = number
  default     = 7
}

variable "github_repository" {
  description = "GitHub repository allowed to assume the CI role, as owner/name."
  type        = string
  default     = "ikramzaldivar/proyecto2"
}

variable "terraform_state_key" {
  description = "Object key of the Terraform state in the backend bucket."
  type        = string
  default     = "fargate/terraform.tfstate"
}
