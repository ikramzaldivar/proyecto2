variable "name_prefix" {
  description = "Prefix shared by every resource name, as <project>-<environment>."
  type        = string
}

variable "account_id" {
  description = "AWS account id, appended to bucket names to keep them globally unique."
  type        = string
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
