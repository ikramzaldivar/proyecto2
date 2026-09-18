output "vpc_id" {
  description = "VPC of the environment."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnets used by the ALB and the Fargate tasks."
  value       = values(aws_subnet.public)[*].id
}

output "database_subnet_ids" {
  description = "Private subnets used by the RDS subnet group."
  value       = values(aws_subnet.database)[*].id
}

output "alb_security_group_id" {
  description = "Security group attached to the public load balancer."
  value       = aws_security_group.alb.id
}

output "frontend_security_group_id" {
  description = "Security group attached to the frontend tasks."
  value       = aws_security_group.frontend.id
}

output "backend_security_group_id" {
  description = "Security group attached to the backend tasks."
  value       = aws_security_group.backend.id
}

output "database_security_group_id" {
  description = "Security group attached to the MariaDB instance."
  value       = aws_security_group.database.id
}

output "s3_vpc_endpoint_id" {
  description = "Gateway endpoint that keeps S3 traffic inside the VPC."
  value       = aws_vpc_endpoint.s3.id
}
