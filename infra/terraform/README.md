# AWS infrastructure

This directory adds the AWS PROD environment without replacing the evaluator's local environment.

- Local DEV remains Docker Compose with MariaDB and MinIO.
- AWS PROD uses separate ECR repositories for the frontend and backend images.
- The DVC PROD remote is a private, encrypted, versioned S3 bucket.
- Approved releases use a separate private bucket with Governance Object Lock.
- Terraform state is stored in a private, encrypted, versioned S3 backend with native locking.
- ECS/Fargate runs the frontend and backend in independent tasks and services.
- A public Application Load Balancer routes `/api/*` to the backend and all other paths to the frontend.
- RDS MariaDB runs in private database subnets and manages its master password in Secrets Manager.
- Backend connections to RDS require TLS and verify the endpoint with the AWS global RDS CA bundle.
- Uploaded portal images use a dedicated private S3 bucket through the backend task role.
- Fargate tasks use public subnets and public IPs for outbound ECR/S3 access, but their security groups accept inbound traffic only from the ALB. This avoids a NAT Gateway for this academic environment.

## Authentication

Use temporary AWS credentials. Do not store access keys, secrets or tokens in this repository.

```bash
export AWS_PROFILE=proyecto2-terraform
export AWS_REGION=us-east-2
```

## Initialize the remote backend

```bash
terraform init \
  -backend-config=backend.hcl.example \
  -backend-config="profile=proyecto2-terraform"
```

When migrating an existing local state, add `-migrate-state` and confirm that Terraform should copy the state to S3.

## Validate before creating resources

Create an ignored `terraform.tfvars` file with the immutable tag pushed to both ECR repositories:

```hcl
container_image_tag = "replace-with-git-sha"
```

```bash
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Review the plan and its recurring-cost resources before running `terraform apply tfplan`. Terraform state, variable and plan files are ignored by Git.

After apply:

```bash
terraform output -raw application_url
aws ecs describe-services \
  --cluster proyecto2-prod \
  --services frontend backend \
  --region us-east-2
```

The local evaluator flow remains unchanged:

```bash
docker compose up --build
```
