# AWS infrastructure

This directory adds the AWS PROD environment without replacing the evaluator's local environment.

- Local DEV remains Docker Compose with MariaDB and MinIO.
- AWS PROD uses separate ECR repositories for the frontend and backend images.
- The DVC PROD remote is a private, encrypted, versioned S3 bucket.
- Approved releases use a separate private bucket with Governance Object Lock.
- Terraform state is stored in a private, encrypted, versioned S3 backend with native locking.
- ECS/Fargate, networking, RDS and the load balancer are added in the next stage.

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

```bash
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Review the plan before running `terraform apply`. Terraform state and plan files are ignored by Git.
