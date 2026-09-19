# Despliegue

Cómo publicar una versión nueva del portal en AWS y cómo diagnosticarlo cuando falla.

Para el detalle de los recursos de infraestructura, ver [`infra/terraform/README.md`](infra/terraform/README.md).

## Cómo está desplegado

| Pieza | Dónde |
|---|---|
| Frontend y backend | ECS Fargate, tareas y servicios independientes |
| Enrutamiento | ALB público: `/api/*` al backend, el resto al frontend |
| Base de datos | RDS MariaDB en subredes privadas |
| Imágenes del portal | Bucket S3 `proyecto2-prod-images-<cuenta>` |
| Imágenes de contenedor | ECR: `proyecto2-prod-frontend` y `proyecto2-prod-backend` |
| Estado de Terraform | Bucket S3 `proyecto2-prod-tfstate-<cuenta>`, con lock nativo |

Frontend y backend comparten **la misma etiqueta de imagen**, definida en la variable `container_image_tag`.

## Requisitos

- AWS CLI v2, Terraform >= 1.10, Docker
- Un perfil de AWS con credenciales temporales

```bash
export AWS_PROFILE=<tu-perfil>
export AWS_REGION=us-east-2
export AWS_PAGER=""
aws sts get-caller-identity
```

## 1. Construir y publicar las imágenes

La etiqueta es el SHA corto del commit. Las etiquetas de ECR son **inmutables**: una vez publicada no se puede sobrescribir, hay que hacer un commit nuevo.

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$ACCOUNT.dkr.ecr.us-east-2.amazonaws.com"
TAG=$(git rev-parse --short=12 HEAD)

aws ecr get-login-password --region us-east-2 \
  | docker login --username AWS --password-stdin "$REGISTRY"
```

> **Construye siempre con `--platform linux/amd64`.** Las task definitions declaran `cpu_architecture = "X86_64"`. Desde una Mac con Apple Silicon, una imagen ARM se publica sin error pero la tarea muere al arrancar con `exec format error`.

```bash
docker build --platform linux/amd64 -t "$REGISTRY/proyecto2-prod-backend:$TAG" ./backend
docker push "$REGISTRY/proyecto2-prod-backend:$TAG"

docker build --platform linux/amd64 -t "$REGISTRY/proyecto2-prod-frontend:$TAG" ./frontend
docker push "$REGISTRY/proyecto2-prod-frontend:$TAG"
```

## 2. Desplegar

Terraform tiene dos raíces, `infra/terraform/envs/dev` y `infra/terraform/envs/prod`, y **solo `prod` está aplicada**: no corras un `apply` en `dev`. Los módulos compartidos viven en `infra/terraform/modules/`.

```bash
cd infra/terraform/envs/prod
echo "container_image_tag = \"$TAG\"" > terraform.tfvars

terraform init -backend-config=backend.hcl.example
terraform plan -out=tfplan
```

Revisa el plan antes de aplicar. Un despliegue normal solo cambia las task definitions y los servicios. **Si aparece algo en `destroy`, no apliques**: compártelo con el equipo.

```bash
terraform apply tfplan
```

## 3. Verificar

```bash
aws ecs describe-services --cluster proyecto2-prod --services frontend backend \
  --query 'services[].{service:serviceName,running:runningCount,desired:desiredCount}' \
  --output table

curl -s "$(terraform -chdir=infra/terraform/envs/prod output -raw application_url)/api/health"
```

`running` debe igualar a `desired` en ambos, y `/api/health` responder `{"status":"ok","database":"connected"}`.

## 4. Volver a una versión anterior

No hace falta reconstruir nada: las imágenes viejas siguen en ECR.

```bash
# Qué etiqueta está desplegada ahora
aws ecs describe-task-definition --task-definition proyecto2-prod-backend \
  --query 'taskDefinition.containerDefinitions[?name==`backend`].image | [0]' --output text

# Etiquetas disponibles
aws ecr describe-images --repository-name proyecto2-prod-backend \
  --query 'sort_by(imageDetails,&imagePushedAt)[-10:].imageTags' --output text
```

Pones la etiqueta anterior en `infra/terraform/envs/prod/terraform.tfvars` y repites el paso 2.

## 5. Cuando falla

**Logs de la aplicación** — CloudWatch, grupos `/ecs/proyecto2-prod/frontend` y `/ecs/proyecto2-prod/backend`:

```bash
aws logs tail /ecs/proyecto2-prod/backend --since 15m --follow
```

**Por qué no arranca una tarea** — los eventos del servicio dicen más que los logs:

```bash
aws ecs describe-services --cluster proyecto2-prod --services backend \
  --query 'services[0].events[:10]' --output table
```

**Razón de la última parada**:

```bash
TASK=$(aws ecs list-tasks --cluster proyecto2-prod --service-name backend \
  --desired-status STOPPED --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster proyecto2-prod --tasks "$TASK" \
  --query 'tasks[0].{stopped:stoppedReason,containers:containers[].reason}'
```

Síntomas frecuentes:

| Qué ves | Causa probable |
|---|---|
| `exec format error` | La imagen se construyó para ARM. Reconstruye con `--platform linux/amd64` |
| La tarea arranca y muere en bucle | Falta una variable de entorno, o el backend no alcanza RDS |
| El ALB devuelve 503 | No hay tareas sanas en el target group |
| `terraform plan` pide destruir cosas | El state no coincide con la rama. Confirma que estás en la rama correcta antes de aplicar |

## Reglas

- La infraestructura se cambia solo por Terraform, en una rama con PR. Nada a mano en la consola.
- No subir `terraform.tfvars`, `.tfstate`, planes ni credenciales.
- No ejecutar `terraform destroy`.
- No borrar RDS, los buckets de S3, ECR, Secrets Manager ni el estado de Terraform.
- Comparte el `terraform plan` antes de un cambio grande.
