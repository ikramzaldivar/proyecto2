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
  default     = 90
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

variable "backup_retention_days" {
  description = "Days RDS keeps automated backups."
  type        = number
  # 1 y no 7: la cuenta esta en el plan Free Tier y RDS rechaza cualquier valor
  # mayor (FreeTierRestrictionError al aplicar, 2026-09-18). Para subirlo hay
  # que hacer dos cosas, en este orden: (1) cambiar el plan de la cuenta en
  # AWS y (2) DESPUES subir este valor (p. ej. a 7) en un PR y aplicar. Con el
  # plan actual, terraform apply falla aunque se cambie el numero.
  default = 1
}
