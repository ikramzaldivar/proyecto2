output "ecr_repository_urls" {
  description = "ECR repositories used by the independent Fargate containers."
  value       = module.registry.repository_urls
}

output "app_images_bucket" {
  description = "Private S3 bucket used by the deployed annotation portal."
  value       = module.storage.app_images_bucket
}

output "dvc_prod_bucket" {
  description = "Private, versioned S3 bucket used as the DVC remote of this environment."
  value       = module.storage.dvc_bucket
}

output "dataset_releases_bucket" {
  description = "Private S3 bucket with Governance Object Lock for approved releases."
  value       = module.storage.releases_bucket
}

output "application_url" {
  description = "Public URL of the annotation portal."
  value       = "http://${module.service.alb_dns_name}"
}

output "ecs_cluster_name" {
  description = "ECS cluster that runs the independent frontend and backend services."
  value       = module.service.cluster_name
}

output "rds_endpoint" {
  description = "Private MariaDB endpoint used by the backend."
  value       = module.database.endpoint
}

output "s3_vpc_endpoint_id" {
  description = "Gateway endpoint that keeps S3 traffic inside the VPC."
  value       = module.network.s3_vpc_endpoint_id
}
