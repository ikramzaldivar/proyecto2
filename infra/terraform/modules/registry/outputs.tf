output "repository_urls" {
  description = "ECR repositories used by the independent Fargate containers."
  value       = { for name, repository in aws_ecr_repository.app : name => repository.repository_url }
}
