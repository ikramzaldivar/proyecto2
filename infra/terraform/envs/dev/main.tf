/**
 * DEV environment. Same modules as PROD, sized smaller and on its own network
 * range.
 *
 * WARNING: this environment is NOT applied. Bringing it up creates its own
 * RDS instance, ALB and two Fargate services, which is real monthly cost. It
 * is here so that the DEV/PROD split genuinely exists in code and changes can
 * be tried before touching PROD, but it gets applied only when someone
 * decides to pay for it.
 *
 * It declares no state bucket and no administrator role: those are
 * account-wide and live in envs/prod/account.tf. DEV uses the SAME bucket
 * under a different key (see backend.hcl.example).
 */

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
}

module "network" {
  source = "../../modules/network"

  name_prefix        = local.name_prefix
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  allowed_http_cidrs = var.allowed_http_cidrs
}

module "storage" {
  source = "../../modules/storage"

  name_prefix            = local.name_prefix
  account_id             = local.account_id
  release_retention_days = var.release_retention_days
}

module "registry" {
  source = "../../modules/registry"

  name_prefix           = local.name_prefix
  image_retention_count = var.ecr_image_retention_count
}

module "database" {
  source = "../../modules/database"

  name_prefix       = local.name_prefix
  subnet_ids        = module.network.database_subnet_ids
  security_group_id = module.network.database_security_group_id
  instance_class    = var.db_instance_class
  db_name           = var.db_name
  db_username       = var.db_username
}

module "service" {
  source = "../../modules/service"

  name_prefix = local.name_prefix
  aws_region  = var.aws_region

  vpc_id                     = module.network.vpc_id
  public_subnet_ids          = module.network.public_subnet_ids
  alb_security_group_id      = module.network.alb_security_group_id
  frontend_security_group_id = module.network.frontend_security_group_id
  backend_security_group_id  = module.network.backend_security_group_id

  ecr_repository_urls   = module.registry.repository_urls
  container_image_tag   = var.container_image_tag
  service_desired_count = var.service_desired_count
  log_retention_days    = var.log_retention_days

  db_host       = module.database.address
  db_port       = module.database.port
  db_name       = var.db_name
  db_username   = var.db_username
  db_secret_arn = module.database.master_user_secret_arn

  app_images_bucket     = module.storage.app_images_bucket
  app_images_bucket_arn = module.storage.app_images_bucket_arn
}
