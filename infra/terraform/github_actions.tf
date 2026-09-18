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
      values   = ["repo:${var.github_repository}:*"]
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
