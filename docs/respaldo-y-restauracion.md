# Respaldo y restauración

Qué datos tiene el proyecto, dónde viven, cómo se respaldan y cómo se
restauran. Todo lo de abajo se probó en un clon limpio de `main` el
18 de septiembre de 2026 (ver [Pruebas realizadas](#pruebas-realizadas)).

Hay tres cosas que perder y las tres se restauran distinto:

| Dato | Local (`docker compose`) | Producción (AWS) | Cómo se restaura |
|---|---|---|---|
| **Base de datos** (imágenes registradas, anotaciones, categorías) | Volumen `mariadb_data` | RDS `proyecto2-prod-mariadb`, respaldo automático de **1 día** | Dump SQL / snapshot de RDS |
| **Imágenes del portal** (los archivos que suben los usuarios) | Volumen `minio_data`, bucket `image-annotations` | S3 `proyecto2-prod-images-<cuenta>`, **versionado** | `mc mirror` / `aws s3 sync` o recuperar versión |
| **Dataset y reportes de calidad** (COCO, imágenes del dataset, `release.json`, `embeddings.json`) | Cache `.dvc/cache` + remoto `dev` (MinIO local) | Remoto DVC `s3://proyecto2-prod-dvc-<cuenta>`, versionado | `dvc pull -r prod` |
| **Releases aprobados** | — | S3 `proyecto2-prod-releases-<cuenta>` con Object Lock | Copiar del bucket; protegido contra borrado y sobrescritura normales durante la retención |

La base de datos y las imágenes del portal van juntas: las filas de `images`
apuntan a llaves de objetos. Respáldalas y restáuralas **del mismo momento**,
o quedarán registros que apuntan a archivos que no existen (o al revés).

## 1. Base de datos (MariaDB)

### Local

Respaldo (deja un `.sql` fuera del contenedor):

```bash
docker compose exec -T mariadb mariadb-dump -uroot -ppassword \
  --single-transaction --routines image_repo > backup-image_repo-$(date +%F).sql
```

Restaurar sobre la base vacía o encima de la existente:

```bash
docker compose exec -T mariadb mariadb -uroot -ppassword \
  -e "DROP DATABASE IF EXISTS image_repo; CREATE DATABASE image_repo;"
docker compose exec -T mariadb mariadb -uroot -ppassword image_repo < backup-image_repo-YYYY-MM-DD.sql
curl -s localhost:3100/api/health     # debe decir "database":"connected"
```

Verificar que volvió lo mismo (cuenta filas por tabla):

```bash
docker compose exec -T mariadb mariadb -uroot -ppassword -N image_repo \
  -e "SELECT CONCAT('SELECT \"', table_name, '\", COUNT(*) FROM \`', table_name, '\`;') FROM information_schema.tables WHERE table_schema='image_repo' AND table_type='BASE TABLE'" \
  | docker compose exec -T mariadb mariadb -uroot -ppassword image_repo
```

`docker compose down -v` borra el volumen y con él la base. Si necesitas
reiniciar desde cero, haz el dump antes.

### Producción (RDS)

RDS toma un respaldo automático diario y lo conserva **1 día** (variable
`backup_retention_days`, con valor 1 en `infra/terraform/envs/prod/variables.tf`:
la cuenta está en Free Tier y RDS rechaza un valor mayor).
Antes de cualquier cambio arriesgado toma un snapshot manual, que no caduca:

```bash
export AWS_PROFILE=<tu-perfil> AWS_REGION=us-east-2 AWS_PAGER=""

aws rds create-db-snapshot \
  --db-instance-identifier proyecto2-prod-mariadb \
  --db-snapshot-identifier proyecto2-prod-mariadb-$(date +%Y%m%d-%H%M)

aws rds describe-db-snapshots --db-instance-identifier proyecto2-prod-mariadb \
  --query 'DBSnapshots[].{id:DBSnapshotIdentifier,estado:Status,fecha:SnapshotCreateTime}' --output table
```

Restaurar **nunca sobrescribe la instancia actual**: RDS crea una instancia
nueva a partir del snapshot. Eso cuesta dinero mientras exista y hay que
apuntar el backend a ella (o volcar sus datos a la original). Es una decisión
de equipo: avisa antes de hacerlo.

```bash
# Crea proyecto2-prod-mariadb-restore desde el snapshot, en la misma red que la original
SUBNET_GROUP=$(aws rds describe-db-instances --db-instance-identifier proyecto2-prod-mariadb --query 'DBInstances[0].DBSubnetGroup.DBSubnetGroupName' --output text)
SG=$(aws rds describe-db-instances --db-instance-identifier proyecto2-prod-mariadb --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text)

aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier proyecto2-prod-mariadb-restore \
  --db-snapshot-identifier <id-del-snapshot> \
  --db-subnet-group-name "$SUBNET_GROUP" \
  --vpc-security-group-ids "$SG" \
  --no-publicly-accessible
```

Después: o cambias el endpoint que usa el backend (por Terraform, en PR) o
haces un `mariadb-dump` de la instancia restaurada hacia la original y borras
la restaurada. RDS está en subredes privadas: el dump tiene que correr desde
dentro de la VPC (una tarea ECS con `execute-command`, no desde tu laptop).

**Riesgos actuales, documentados y no corregidos aquí** (tocar RDS requiere
acuerdo de equipo): retención de 1 día, `deletion_protection = false` y
`skip_final_snapshot = true`. Si alguien destruye la instancia, no queda
snapshot final. La recomendación es subir la retención a 7 días y activar
`deletion_protection`, en un PR aparte. Subir la retención exige antes cambiar el
plan de la cuenta de AWS: con Free Tier, `terraform apply` falla aunque se cambie
el número (ver el comentario de `backup_retention_days`).

## 2. Imágenes del portal

### Local (MinIO)

El bucket es `image-annotations`. `mc` viene dentro de la imagen de MinIO;
se hace el espejo dentro del contenedor y se copia hacia afuera:

```bash
# Respaldo -> ./backup-minio/image-annotations/
docker compose exec minio sh -c '
  mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null &&
  mc mirror --overwrite local/image-annotations /tmp/backup/image-annotations'
docker compose cp minio:/tmp/backup ./backup-minio
```

```bash
# Restaurar desde ./backup-minio/
docker compose cp ./backup-minio minio:/tmp/restore
docker compose exec minio sh -c '
  mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null &&
  mc mb --ignore-existing local/image-annotations &&
  mc mirror --overwrite /tmp/restore/image-annotations local/image-annotations &&
  mc ls --recursive local/image-annotations | wc -l'
```

### Producción (S3)

El bucket está versionado: sobrescribir o borrar un objeto no lo destruye,
crea una versión nueva o un *delete marker*. Casos:

```bash
BUCKET=proyecto2-prod-images-$(aws sts get-caller-identity --query Account --output text)

# Copia completa del estado actual a disco (respaldo frío)
aws s3 sync "s3://$BUCKET" ./backup-images-prod

# Restaurar la copia completa
aws s3 sync ./backup-images-prod "s3://$BUCKET"

# Un objeto sobrescrito: listar versiones y recuperar una anterior
aws s3api list-object-versions --bucket "$BUCKET" --prefix <llave> \
  --query 'Versions[].{version:VersionId,fecha:LastModified,actual:IsLatest}' --output table
aws s3api get-object --bucket "$BUCKET" --key <llave> --version-id <VersionId> recuperado.jpg

# Un objeto borrado: quitar el delete marker lo revive
aws s3api list-object-versions --bucket "$BUCKET" --prefix <llave> \
  --query 'DeleteMarkers[?IsLatest].{marker:VersionId}' --output text
aws s3api delete-object --bucket "$BUCKET" --key <llave> --version-id <marker>
```

## 3. Dataset y reportes de calidad (DVC)

### Qué vive en git y qué en DVC

| En git (siempre viene con `git clone`) | En el remoto DVC (hay que hacer `dvc pull`) |
|---|---|
| `dvc.yaml`, `dvc.lock`, `*.dvc` (los punteros) | `data/raw/images/` (las imágenes del dataset) |
| `quality/quality.yaml` (la política) | `data/annotations/coco-dataset.json` |
| `reports/versions.json`, `reports/metrics.json` | `reports/release.json`, `reports/embeddings.json`, `reports/image_hashes.json`, `reports/analyzers/` |

Por eso un clon recién hecho, si se levanta solo con `docker compose up`, muestra las
vistas de calidad sin datos y el Copilot contesta que faltan artefactos. No está roto:
faltan `dvc pull -r prod` y `dvc repro`. El flujo vigente es `make up`, que hace las tres
cosas en orden (`dvc pull -r prod` → `dvc repro` → `docker compose up --build`).

### Remotos

| Remoto | URL | Para qué |
|---|---|---|
| `prod` | `s3://proyecto2-prod-dvc-<cuenta>` (us-east-2) | **La fuente de verdad.** Compartido, versionado |
| `dev` | `s3://proyecto2-dvc-dev` en `http://localhost:9000` | MinIO local de cada quien. **No es respaldo ni es compartido** |

### Configurar DVC la primera vez

```bash
python3 -m venv ~/.dvc-venv && ~/.dvc-venv/bin/pip install "dvc[s3]"
alias dvc=~/.dvc-venv/bin/dvc
```

Credenciales: **solo** por variables de entorno o por `.dvc/config.local`
(está en `.gitignore`). Nunca en `.dvc/config` ni en un PR.

```bash
# Opción A: el perfil de AWS en el entorno
export AWS_PROFILE=<tu-perfil>

# Opción B: dejarlo fijo en la config local (no se versiona)
dvc remote modify --local prod profile <tu-perfil>
```

### Bajar todo (restaurar el estado actual)

```bash
dvc pull -r prod
dvc status -c -r prod        # "Cache and remote 'prod' are in sync."
dvc repro                    # regenera reports/ desde lo descargado (no-op si ya esta al dia)
make up                      # o docker compose up --build
curl -s localhost:8080/api/quality/overview | head -c 200   # 200 con datasetVersion y totals
```

### Volver a una versión anterior del dataset

`reports/versions.json` guarda, por versión, el commit de git y el hash DVC.
Con eso:

```bash
git checkout <commit-de-versions.json>
dvc pull -r prod             # baja exactamente los archivos de ese commit
dvc repro && make up         # y levanta el portal con ese estado
```

`dvc.lock` fija los hashes de cada etapa, así que `dvc repro` desde ese
commit reproduce el mismo `release.json` (salvo `generated_at`).

### Respaldar hacia el remoto

Después de cada `dvc repro` que cambie algo:

```bash
dvc push -r prod
dvc status -c -r prod
```

Si solo hiciste `dvc push -r dev`, el trabajo está únicamente en tu MinIO
local: nadie más lo tiene y `docker compose down -v` lo borra.

### Releases aprobados

El bucket `proyecto2-prod-releases-<cuenta>` tiene Object Lock en modo
Governance, con una retención de 90 días por defecto en `envs/prod`
(`release_retention_days`). Lo que se publica ahí no se puede borrar ni
sobrescribir mediante operaciones normales durante la retención; solo un usuario
autorizado con permiso explícito de bypass (`s3:BypassGovernanceRetention`)
puede omitirla. Protege contra accidentes y borrados normales, pero no es una
garantía absoluta frente a quien tenga privilegios. Es el respaldo definitivo de
un release; para "restaurarlo" basta copiarlo:

```bash
aws s3 ls s3://proyecto2-prod-releases-$(aws sts get-caller-identity --query Account --output text)/ --recursive
aws s3 cp s3://proyecto2-prod-releases-<cuenta>/<version>/release.json ./
```

## Pruebas realizadas

Clon limpio de `main`, `docker compose up --build`, 18 de septiembre de 2026.

| Qué | Cómo | Resultado |
|---|---|---|
| MariaDB local | `mariadb-dump` (6.9 KB) → `DROP DATABASE` → restaurar | Mismas filas: `categories` 3, `images` 2, `annotations` 0, `__drizzle_migrations` 3. `/api/health` → `database: connected` |
| MinIO local | `mc mirror` a `/tmp/backup` → `mc rm --recursive --force` (0 objetos) → `mc mirror` de vuelta | 3/3 objetos, contenido del archivo de prueba intacto |
| DVC desde `prod` | `dvc pull -r prod` sin cache previa | 700 archivos en 50 s (689 imágenes, COCO de 475 KB, `release.json`, `embeddings.json`, `image_hashes.json`, `analyzers/`). `dvc status -c`: in sync |
| Portal tras el pull | Se reinició solo el backend sobre un stack ya levantado (prueba manual; el flujo reproducible es `dvc pull -r prod` → `dvc repro` → `make up`) | `/api/quality/overview`, `/splits`, `/embeddings` → 200. Copilot: `grounded: true`, "689 imágenes, 1455 cajas y 3 categorías, compuerta pass" |

No se probó la restauración de un snapshot de RDS ni el `s3 sync` completo de
producción: ambos crean recursos que cuestan y el segundo mueve todas las
imágenes reales. Los comandos están arriba; la primera vez que se ejecuten,
anotar aquí el resultado.
