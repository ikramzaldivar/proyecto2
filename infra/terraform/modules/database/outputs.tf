output "endpoint" {
  description = "Private MariaDB endpoint used by the backend, as host:port."
  value       = aws_db_instance.app.endpoint
}

output "address" {
  description = "Hostname of the MariaDB instance."
  value       = aws_db_instance.app.address
}

output "port" {
  description = "Port of the MariaDB instance."
  value       = aws_db_instance.app.port
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the password generated and rotated by RDS."
  value       = aws_db_instance.app.master_user_secret[0].secret_arn
}
