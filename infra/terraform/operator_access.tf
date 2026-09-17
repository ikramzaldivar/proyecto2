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

output "andres_admin_role_arn" {
  description = "Administrator role assumed by Andres."
  value       = aws_iam_role.andres_admin.arn
}