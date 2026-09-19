/**
 * Keyless CI access for GitHub Actions, through OIDC.
 *
 * Account-wide, like the rest of account.tf: one OIDC provider and one CI role
 * per account, not per environment. It also has to sit in the root because its
 * least-privilege policy is scoped to the state bucket declared there.
 *
 * The write permission is deliberately narrow: only the `.tflock` object that
 * S3 native locking creates, so `terraform plan` can take and release the lock
 * without being able to touch the state itself.
 */

locals {
  github_owner     = split("/", var.github_repository)[0]
  github_repo_name = split("/", var.github_repository)[1]
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        # Formato clasico: repo:owner/name:ref
        "repo:${var.github_repository}:*",
        # Formato actual de GitHub: repo:owner@ID/name@ID:ref. Los IDs son
        # numericos e inmutables; sin esta forma el rol rechaza el token.
        "repo:${local.github_owner}@*/${local.github_repo_name}@*:*",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name                 = "${local.name_prefix}-github-actions"
  description          = "Keyless CI role assumed by GitHub Actions through OIDC."
  assume_role_policy   = data.aws_iam_policy_document.github_actions_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "github_actions_read" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "github_actions_state_lock" {
  statement {
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = ["${aws_s3_bucket.terraform_state.arn}/${var.terraform_state_key}.tflock"]
  }
}

resource "aws_iam_role_policy" "github_actions_state_lock" {
  name   = "terraform-state-lock"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_state_lock.json
}

output "github_actions_role_arn" {
  description = "Role assumed by GitHub Actions through OIDC."
  value       = aws_iam_role.github_actions.arn
}
