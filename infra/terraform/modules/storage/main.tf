/**
 * Data buckets of the environment: portal images, DVC remote and approved
 * releases with Object Lock.
 *
 * The Terraform state bucket is NOT here: it is account-wide and is managed
 * from the envs/prod root, because the state that describes it is the one
 * stored inside it.
 *
 * The three buckets share the same hardening (versioning, encryption and
 * public access block), so that part is applied with for_each over
 * `local.hardened_buckets` instead of being repeated three times.
 */

resource "aws_s3_bucket" "app_images" {
  bucket        = "${var.name_prefix}-images-${var.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket" "dvc_prod" {
  bucket        = "${var.name_prefix}-dvc-${var.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket" "releases" {
  bucket              = "${var.name_prefix}-releases-${var.account_id}"
  force_destroy       = false
  object_lock_enabled = true
}

locals {
  hardened_buckets = {
    images   = aws_s3_bucket.app_images.id
    dvc      = aws_s3_bucket.dvc_prod.id
    releases = aws_s3_bucket.releases.id
  }
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = local.hardened_buckets

  bucket = each.value

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.hardened_buckets

  bucket = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.hardened_buckets

  bucket = each.value

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

  depends_on = [aws_s3_bucket_versioning.this]
}
