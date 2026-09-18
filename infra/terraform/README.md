# AWS infrastructure

This directory holds the AWS environments. The local evaluator flow is
unchanged: `docker compose up --build` still runs MariaDB and MinIO.

## Layout

```text
modules/            Reusable building blocks. No environment values inside.
  network/          VPC, subnets, routing, security groups, S3 gateway endpoint
  storage/          Portal images, DVC remote and release buckets
  registry/         ECR repositories with immutable tags
  database/         RDS MariaDB in private subnets
  service/          ALB, ECS cluster, task definitions, services and task roles
envs/               One root per environment. This is where you run Terraform.
  prod/             Applied. Also holds the account-wide resources
  dev/              Defined, NOT applied. See the warning below
```

Modules never read `terraform.tfvars` or the backend: they receive everything
through variables, so the same module builds PROD and DEV.

Each environment has its own state under a different key in the same bucket, so
a `plan` in DEV can never touch PROD.

| | PROD | DEV |
|---|---|---|
| State key | `fargate/terraform.tfstate` | `dev/terraform.tfstate` |
| VPC CIDR | `10.20.0.0/16` | `10.30.0.0/16` |
| Name prefix | `proyecto2-prod-` | `proyecto2-dev-` |
| Log retention | 7 days | 3 days |
| Applied | yes | no |

`envs/prod/account.tf` holds what belongs to the account rather than the
environment: the Terraform state bucket and the cross-account administrator
role. DEV reuses both. The file explains why they are not in a module.

### DEV costs money

`envs/dev` is committed but has never been applied. Running `apply` there
creates its own RDS instance, ALB and two Fargate services — real monthly
spend. Apply it only when someone has decided to pay for it.

## Authentication

Use temporary AWS credentials. Do not store access keys, secrets or tokens in
this repository.

```bash
export AWS_PROFILE=proyecto2-terraform
export AWS_REGION=us-east-2
```

## Running an environment

Always `cd` into the environment first. Running Terraform from this directory
does nothing — there is no root module here.

```bash
cd envs/prod

terraform init \
  -backend-config=backend.hcl.example \
  -backend-config="profile=proyecto2-terraform"
```

Create an ignored `terraform.tfvars` with the immutable tag pushed to both ECR
repositories:

```hcl
container_image_tag = "replace-with-git-sha"
```

```bash
terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
```

Review the plan and its recurring-cost resources before `terraform apply tfplan`.
State, variable and plan files are ignored by Git.

After apply:

```bash
terraform output -raw application_url
aws ecs describe-services \
  --cluster proyecto2-prod \
  --services frontend backend \
  --region us-east-2
```

## The `moved` blocks

`envs/prod/moved.tf` maps every pre-refactor resource address to its new
address inside a module. Terraform reads them during `plan`, so the state is
rewritten in place instead of destroying and recreating the VPC, the database
and the buckets.

The first PROD plan after this refactor must show **0 to add, 0 to change, 0 to
destroy**. If it shows anything else, stop and fix the mapping — do not apply.

Once that plan has been applied, the file can be deleted in a separate PR.

## What the design gets you

- Only port 80 is reachable from the internet. The tasks and the database
  accept traffic only from the security group in front of them.
- ECR tags are immutable, so a rollback is always to a byte-identical image.
- The RDS master password is generated and rotated by RDS in Secrets Manager
  and never passes through Terraform or the state file.
- Backend connections to RDS require TLS and verify the endpoint against the
  AWS global RDS CA bundle.
- S3 traffic leaves through a gateway endpoint, so it never crosses the public
  internet and needs no NAT Gateway.
- Approved dataset releases live in a bucket with Governance Object Lock.
- Fargate tasks sit in public subnets with public IPs for outbound ECR and S3
  access. That avoids a NAT Gateway, which is the right trade for an academic
  environment; production-grade would use private subnets plus NAT.
