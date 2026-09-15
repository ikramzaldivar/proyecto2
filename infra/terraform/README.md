# AWS infrastructure

This directory adds the AWS PROD environment without replacing the evaluator's local environment.

- Local DEV remains Docker Compose with MariaDB and MinIO.
- AWS PROD uses separate ECR repositories for the frontend and backend images.
- The DVC PROD remote is a private, encrypted, versioned S3 bucket.
- Approved releases use a separate private bucket with Governance Object Lock.
- ECS/Fargate, networking, RDS and the load balancer are added in the next stage.

## Authentication

Use temporary AWS credentials. Do not store access keys, secrets or tokens in this repository.

```bash
export AWS_PROFILE=proyecto2-terraform
export AWS_REGION=us-east-2
```

## Validate before creating resources

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Review the plan before running `terraform apply`. Terraform state and plan files are ignored by Git.
