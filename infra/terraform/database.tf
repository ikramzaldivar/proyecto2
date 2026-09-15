resource "aws_db_subnet_group" "app" {
  name       = "${local.name_prefix}-database"
  subnet_ids = values(aws_subnet.database)[*].id
}

resource "aws_db_instance" "app" {
  identifier = "${local.name_prefix}-mariadb"

  engine                 = "mariadb"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 30
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = var.db_name
  username               = var.db_username
  manage_master_user_password = true
  port                   = 3306

  db_subnet_group_name   = aws_db_subnet_group.app.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 1
  auto_minor_version_upgrade = true
  deletion_protection    = false
  skip_final_snapshot    = true
  apply_immediately      = true
}
