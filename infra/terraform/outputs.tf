output "ecr_repository_urls" {
  description = "ECR repositories used by the independent Fargate containers."
  value       = { for name, repository in aws_ecr_repository.app : name => repository.repository_url }
}

output "terraform_state_bucket" {
  description = "Private, versioned bucket used to persist Terraform state."
  value       = aws_s3_bucket.terraform_state.bucket
}

output "app_images_bucket" {
  description = "Private S3 bucket used by the deployed annotation portal."
  value       = aws_s3_bucket.app_images.bucket
}

output "dvc_prod_bucket" {
  description = "Private, versioned S3 bucket used as the DVC PROD remote."
  value       = aws_s3_bucket.dvc_prod.bucket
}

output "dataset_releases_bucket" {
  description = "Private S3 bucket with Governance Object Lock for approved releases."
  value       = aws_s3_bucket.releases.bucket
}

output "application_url" {
  description = "Public URL of the annotation portal."
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecs_cluster_name" {
  description = "ECS cluster that runs the independent frontend and backend services."
  value       = aws_ecs_cluster.app.name
}

output "rds_endpoint" {
  description = "Private MariaDB endpoint used by the backend."
  value       = aws_db_instance.app.endpoint
}
