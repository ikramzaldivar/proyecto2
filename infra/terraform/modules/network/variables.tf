variable "name_prefix" {
  description = "Prefix shared by every resource name, as <project>-<environment>."
  type        = string
}

variable "aws_region" {
  description = "AWS region, used to build the S3 gateway endpoint service name."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC. Each environment needs its own range."
  type        = string
  default     = "10.20.0.0/16"
}

variable "allowed_http_cidrs" {
  description = "CIDR ranges allowed to reach the public HTTP listener."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
