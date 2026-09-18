/**
 * ECR repositories for the frontend and backend images.
 *
 * Tags are IMMUTABLE on purpose: once an image is pushed under a commit SHA,
 * that SHA cannot be overwritten. That is what makes rollback trustworthy.
 */

resource "aws_ecr_repository" "app" {
  for_each = toset(["frontend", "backend"])

  name                 = "${var.name_prefix}-${each.key}"
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
        countNumber = var.image_retention_count
      }
      action = {
        type = "expire"
      }
    }]
  })
}
