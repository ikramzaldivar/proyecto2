variable "name_prefix" {
  description = "Prefix shared by every resource name, as <project>-<environment>."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets that make up the RDS subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group that only allows traffic from the backend tasks."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
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

variable "backup_retention_days" {
  description = "Days RDS keeps automated backups. 1 is the bare minimum; 7 gives a week to notice a bad write."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}
