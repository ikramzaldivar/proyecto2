/**
 * Map of old addresses to new ones.
 *
 * Moving resources into modules changes their address in the state
 * (`aws_vpc.main` becomes `module.network.aws_vpc.main`). Without these
 * blocks Terraform does not recognise the resource in the state and plans to
 * DESTROY the old one and CREATE a new one, taking the VPC, the database and
 * the buckets with it.
 *
 * With them, the plan comes out with zero creations and zero destructions.
 *
 * This replaces running 46 `terraform state mv` commands by hand: it lives in
 * the repo, it is reviewed in the PR, and anyone who clones the repo gets the
 * same result.
 *
 * Once PROD applies cleanly this file can be deleted in a separate PR: the
 * `moved` blocks will have done their job.
 */

# ---------------------------------------------------------------- network

moved {
  from = aws_vpc.main
  to   = module.network.aws_vpc.main
}

moved {
  from = aws_internet_gateway.main
  to   = module.network.aws_internet_gateway.main
}

moved {
  from = aws_subnet.public
  to   = module.network.aws_subnet.public
}

moved {
  from = aws_subnet.database
  to   = module.network.aws_subnet.database
}

moved {
  from = aws_route_table.public
  to   = module.network.aws_route_table.public
}

moved {
  from = aws_route.internet
  to   = module.network.aws_route.internet
}

moved {
  from = aws_route_table_association.public
  to   = module.network.aws_route_table_association.public
}

moved {
  from = aws_vpc_endpoint.s3
  to   = module.network.aws_vpc_endpoint.s3
}

moved {
  from = aws_security_group.alb
  to   = module.network.aws_security_group.alb
}

moved {
  from = aws_security_group.frontend
  to   = module.network.aws_security_group.frontend
}

moved {
  from = aws_security_group.backend
  to   = module.network.aws_security_group.backend
}

moved {
  from = aws_security_group.database
  to   = module.network.aws_security_group.database
}

# ---------------------------------------------------------------- storage
#
# The three hardening rules became a for_each inside the module, which is why
# the destinations carry a key: ["images"], ["dvc"] and ["releases"].

moved {
  from = aws_s3_bucket.app_images
  to   = module.storage.aws_s3_bucket.app_images
}

moved {
  from = aws_s3_bucket_versioning.app_images
  to   = module.storage.aws_s3_bucket_versioning.this["images"]
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.app_images
  to   = module.storage.aws_s3_bucket_server_side_encryption_configuration.this["images"]
}

moved {
  from = aws_s3_bucket_public_access_block.app_images
  to   = module.storage.aws_s3_bucket_public_access_block.this["images"]
}

moved {
  from = aws_s3_bucket.dvc_prod
  to   = module.storage.aws_s3_bucket.dvc_prod
}

moved {
  from = aws_s3_bucket_versioning.dvc_prod
  to   = module.storage.aws_s3_bucket_versioning.this["dvc"]
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.dvc_prod
  to   = module.storage.aws_s3_bucket_server_side_encryption_configuration.this["dvc"]
}

moved {
  from = aws_s3_bucket_public_access_block.dvc_prod
  to   = module.storage.aws_s3_bucket_public_access_block.this["dvc"]
}

moved {
  from = aws_s3_bucket.releases
  to   = module.storage.aws_s3_bucket.releases
}

moved {
  from = aws_s3_bucket_versioning.releases
  to   = module.storage.aws_s3_bucket_versioning.this["releases"]
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.releases
  to   = module.storage.aws_s3_bucket_server_side_encryption_configuration.this["releases"]
}

moved {
  from = aws_s3_bucket_public_access_block.releases
  to   = module.storage.aws_s3_bucket_public_access_block.this["releases"]
}

moved {
  from = aws_s3_bucket_object_lock_configuration.releases
  to   = module.storage.aws_s3_bucket_object_lock_configuration.releases
}

# --------------------------------------------------------------- registry

moved {
  from = aws_ecr_repository.app
  to   = module.registry.aws_ecr_repository.app
}

moved {
  from = aws_ecr_lifecycle_policy.app
  to   = module.registry.aws_ecr_lifecycle_policy.app
}

# --------------------------------------------------------------- database

moved {
  from = aws_db_subnet_group.app
  to   = module.database.aws_db_subnet_group.app
}

moved {
  from = aws_db_instance.app
  to   = module.database.aws_db_instance.app
}

# ---------------------------------------------------------------- service

moved {
  from = aws_lb.app
  to   = module.service.aws_lb.app
}

moved {
  from = aws_lb_target_group.frontend
  to   = module.service.aws_lb_target_group.frontend
}

moved {
  from = aws_lb_target_group.backend
  to   = module.service.aws_lb_target_group.backend
}

moved {
  from = aws_lb_listener.http
  to   = module.service.aws_lb_listener.http
}

moved {
  from = aws_lb_listener_rule.backend_api
  to   = module.service.aws_lb_listener_rule.backend_api
}

moved {
  from = aws_ecs_cluster.app
  to   = module.service.aws_ecs_cluster.app
}

moved {
  from = aws_cloudwatch_log_group.app
  to   = module.service.aws_cloudwatch_log_group.app
}

moved {
  from = aws_ecs_task_definition.frontend
  to   = module.service.aws_ecs_task_definition.frontend
}

moved {
  from = aws_ecs_task_definition.backend
  to   = module.service.aws_ecs_task_definition.backend
}

moved {
  from = aws_ecs_service.frontend
  to   = module.service.aws_ecs_service.frontend
}

moved {
  from = aws_ecs_service.backend
  to   = module.service.aws_ecs_service.backend
}

moved {
  from = aws_iam_role.ecs_execution
  to   = module.service.aws_iam_role.ecs_execution
}

moved {
  from = aws_iam_role_policy_attachment.ecs_execution
  to   = module.service.aws_iam_role_policy_attachment.ecs_execution
}

moved {
  from = aws_iam_role_policy.ecs_execution_secret
  to   = module.service.aws_iam_role_policy.ecs_execution_secret
}

moved {
  from = aws_iam_role.frontend_task
  to   = module.service.aws_iam_role.frontend_task
}

moved {
  from = aws_iam_role.backend_task
  to   = module.service.aws_iam_role.backend_task
}

moved {
  from = aws_iam_role_policy.backend_images
  to   = module.service.aws_iam_role_policy.backend_images
}
