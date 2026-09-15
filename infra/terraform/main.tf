locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
}

resource "aws_ecr_repository" "app" {
  for_each = toset(["frontend", "backend"])

  name                 = "${local.name_prefix}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each = aws_ecr_repository.app

  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the most recent container images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_image_retention_count
      }
      action = {
        type = "expire"
      }
    }]
  })
}

resource "aws_s3_bucket" "dvc_prod" {
  bucket        = "${local.name_prefix}-dvc-${local.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "dvc_prod" {
  bucket = aws_s3_bucket.dvc_prod.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dvc_prod" {
  bucket = aws_s3_bucket.dvc_prod.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dvc_prod" {
  bucket = aws_s3_bucket.dvc_prod.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "releases" {
  bucket              = "${local.name_prefix}-releases-${local.account_id}"
  force_destroy       = false
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "releases" {
  bucket = aws_s3_bucket.releases.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "releases" {
  bucket = aws_s3_bucket.releases.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_object_lock_configuration" "releases" {
  bucket = aws_s3_bucket.releases.id

  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.release_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.releases]
}
