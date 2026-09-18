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
