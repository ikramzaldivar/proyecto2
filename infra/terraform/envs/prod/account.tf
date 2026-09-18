/**
 * Account-wide resources, not environment ones.
 *
 * They live in the PROD root rather than in a module for two reasons:
 *
 * 1. The state bucket is the one holding THIS state. Putting it in a reusable
 *    module would invite DEV to create its own, when the right thing is for
 *    DEV to use the same bucket under a different key (see
 *    envs/dev/backend.hcl.example).
 * 2. The cross-account administrator role is one per account. Inside a
 *    per-environment module, DEV would create a second role under a different
 *    name and we would have two front doors instead of one.
 *
 * Extracting them into a separate `bootstrap` stack is the natural next step,
 * but that needs `state rm` + `import`, which is the most dangerous operation
 * of all. It belongs in its own PR, not mixed into this refactor.
 */

resource "aws_s3_bucket" "terraform_state" {
  bucket        = "${local.name_prefix}-tfstate-${local.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "andres_admin_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::689351349723:user/andres"
      ]
    }
  }
}

resource "aws_iam_role" "andres_admin" {
  name                 = "${local.name_prefix}-administrator"
  description          = "Temporary cross-account administrator role for Andres."
  assume_role_policy   = data.aws_iam_policy_document.andres_admin_trust.json
  max_session_duration = 3600

  tags = {
    Purpose = "Proyecto2 infrastructure administration"
    Owner   = "Andres"
  }
}

resource "aws_iam_role_policy_attachment" "andres_admin" {
  role       = aws_iam_role.andres_admin.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
