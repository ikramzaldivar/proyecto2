output "app_images_bucket" {
  description = "Private S3 bucket used by the deployed annotation portal."
  value       = aws_s3_bucket.app_images.bucket
}

output "app_images_bucket_arn" {
  description = "ARN of the portal image bucket, used to scope the backend task policy."
  value       = aws_s3_bucket.app_images.arn
}

output "dvc_bucket" {
  description = "Private, versioned S3 bucket used as the DVC PROD remote."
  value       = aws_s3_bucket.dvc_prod.bucket
}

output "releases_bucket" {
  description = "Private S3 bucket with Governance Object Lock for approved releases."
  value       = aws_s3_bucket.releases.bucket
}
