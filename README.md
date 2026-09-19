# Calidad y versionado de datasets (Proyecto 2)

Un **dataset COCO versionado y liberable**. Parte del COCO que produjo el Proyecto 1 (el portal de
anotación, ahora en [docs/portal-mp1.md](docs/portal-mp1.md)), lo somete a analizadores de calidad y a
una compuerta que puede **bloquear el release**, lo divide en train/val/test de forma reproducible y lo
versiona con DVC. Encima hay una aplicación web de seis pantallas, un Dataset Copilot (servidor MCP más
agente de solo lectura) y la infraestructura en Terraform.

| Tier | Qué hace | Dónde vive |
|---|---|---|
| 1. Ingesta | COCO crudo del Proyecto 1, con volumen real de anotación | `data/` (versionado con DVC) |
| 2. Analizadores | Objetos pequeños, desbalance, duplicados por pHash, cajas inválidas, sesgo espacial | `quality/src/dataset_quality/analyzers/` |
| 3. Compuerta | `quality.yaml` con severidad `warn` / `fail`; un `fail` bloquea el release | `quality/quality.yaml`, `policy/quality_gate.py` |
| 4. Split | train/val/test estratificado, reproducible por semilla, sin fuga | `quality/src/dataset_quality/splits/` |
| 5. Versionado | Pipeline de DVC, remotos DEV (MinIO) y PROD (S3), releases con versión semántica | `dvc.yaml`, `reports/versions.json` |

**Para levantar todo:**

```bash
make setup   # una sola vez: dependencias
make up      # dvc pull -r prod → dvc repro → docker compose up --build
```

Luego abre <http://localhost:8080/overview>. Sin acceso a los remotos de DVC, usa `make demo`. Si no
tienes `make`, sigue [Arranque desde cero](#arranque-desde-cero): son los mismos comandos, uno por uno.

## Requisitos

- Docker con Compose v2, Git, Python **3.12**, Node 20 o superior.
- Un shell tipo POSIX: Linux, macOS, WSL o Git Bash en Windows (las etapas de `dvc.yaml` usan `PYTHONPATH=… python`).
- Para `dvc pull -r prod`: credenciales de AWS con lectura sobre el bucket de PROD (`AWS_PROFILE` o variables `AWS_*`). Sin ellas, usa `make demo`.

## Arranque desde cero

Cada comando se puede copiar y pegar tal cual, en este orden.

**1. Clonar y configurar el entorno**

```bash
git clone https://github.com/ikramzaldivar/proyecto2.git && cd proyecto2
cp .env.example .env
```

`.env.example` trae valores de desarrollo que ya funcionan con `docker compose`; no hay que editar nada
para arrancar.

**2. Instalar dependencias**

```bash
pip install -e "quality/[dev]"
pip install "dvc[s3]"
npm --prefix backend ci
npm --prefix frontend ci
```

El paquete de `quality/` lo usan las etapas de DVC; `backend/` se necesita porque la etapa `embeddings`
del pipeline corre en Node.

**3. Traer los datos y regenerar los artefactos**

```bash
export AWS_PROFILE=<tu-perfil>   # credenciales con lectura sobre el bucket de PROD
dvc pull -r prod
dvc repro
```

`dvc pull -r prod` descarga las imágenes y el COCO (`data/raw`, `data/annotations`). `dvc repro` corre el
pipeline y escribe en `reports/` los archivos que lee el portal: `release.json`, `embeddings.json` y los
reportes de cada analizador. Este paso **no se puede saltar**: esos archivos son **salidas del pipeline**
y no van en git, así que sin correrlo las seis pantallas de calidad arrancan en «Sin datos».

Si `dvc repro` termina con error, la compuerta de calidad quedó en `fail` y el release **no** se generó
(es lo esperado: ver [Compuerta](#compuerta-de-calidad-y-pipeline)).

**4. Levantar la aplicación**

```bash
docker compose up --build
```

Levanta MariaDB, MinIO, el backend y el frontend. Cuando termine de construir, abre las pantallas de la
siguiente tabla.

**Sin acceso a los remotos de DVC**

```bash
make demo
```

Genera un dataset **sintético** (~40 imágenes, en `demo/`, ignorado por git), corre sobre él el mismo
pipeline con una política más laxa (`quality/quality.demo.yaml`, marcada *SOLO DEMO*) y levanta la app
apuntando a esos artefactos. Sirve para ver las seis pantallas con cifras; **no** es un release del
proyecto.

## Rutas de la aplicación

El frontend se sirve en <http://localhost:8080>; el backend, en <http://localhost:3100>.

| Ruta | Pantalla | Qué muestra |
|---|---|---|
| `/overview` | Overview | Imágenes, cajas, categorías, checks fallidos y estado de la compuerta |
| `/analyzers` | Analyzers | Cinco pestañas: objetos pequeños, desbalance, duplicados, cajas inválidas, sesgo espacial |
| `/splits` | Splits | Distribución de clases por split y resultado del chequeo de fuga |
| `/versions` | Versions | Línea de tiempo de versiones, diff entre dos y estado DEV / PROD |
| `/settings` | Settings | Edita los umbrales de `quality.yaml`; el cambio persiste y aplica en la siguiente corrida |
| `/copilot` | Copilot | Preguntas sobre el dataset, con las tool calls y la versión citada |
| `/analytics` | Analytics | PCA precomputado offline; hover muestra la imagen y el filtro por clase corre en el navegador |

Las rutas del portal del Proyecto 1 (`/dashboard`, `/upload`, `/search`) siguen disponibles; están
descritas en [docs/portal-mp1.md](docs/portal-mp1.md).

## Compuerta de calidad y pipeline

`dvc.yaml` define cuatro etapas encadenadas; `dvc repro` solo rehace las que cambiaron:

| Etapa | Entrada | Salida |
|---|---|---|
| `hash_images` | `data/raw` | `reports/image_hashes.json` (pHash de cada imagen) |
| `analyze` | COCO, hashes, `quality/quality.yaml` | `reports/analyzers/`, `reports/metrics.json` |
| `embeddings` | COCO | `reports/embeddings.json` (PCA offline) |
| `release` | COCO, analizadores | `reports/release.json`: compuerta, splits y fuga |

La política vive en [`quality/quality.yaml`](quality/quality.yaml): umbral y severidad por check. El mínimo del
curso es **300 imágenes por clase en al menos 2 clases**, con severidad `fail`. Un `fail` termina la etapa
`release` con código de salida distinto de cero, DVC no registra el release y la promoción se detiene.

## Versiones y releases

`reports/versions.json` es el historial de releases (sí se versiona en git). Para cortar una versión:

```bash
DATASET_VERSION=v1.1.0 dvc repro -f release
PYTHONPATH=quality/src python pipeline/register_version.py \
  --release reports/release.json --config quality/quality.yaml \
  --registry reports/versions.json --version v1.1.0
```

Exige versión semántica (`vX.Y.Z`) y **no registra** un release cuya compuerta quedó en `fail`. Con
`--dev-hash` y `--prod-hash` se marca la versión como empujada a cada remoto una vez hecho el `dvc push`.

## Dataset Copilot y servidor MCP

El Copilot responde preguntas sobre el dataset usando **herramientas de solo lectura** (9 en total) y las
cifras salen siempre de esas herramientas, nunca del modelo. Cada respuesta cita la versión consultada y
las herramientas usadas. Además de la pantalla `/copilot`:

```bash
cd backend
npm run copilot:demo   # hace preguntas de ejemplo contra los artefactos de reports/
npm run mcp            # servidor MCP por stdio (initialize, tools/list, tools/call)
```

| Variable | Para qué sirve | Por defecto |
|---|---|---|
| `QUALITY_ARTIFACTS_DIR` | Carpeta con `release.json`, `versions.json` y `embeddings.json` | `../reports` |
| `COPILOT_PROVIDER` | `none`, `anthropic` o `mistral` | `none` |
| `COPILOT_API_KEY` | Clave del proveedor (nunca se versiona; va en `.env`) | vacía |
| `COPILOT_MODEL` | Modelo del proveedor; vacío usa el modelo por defecto | vacío |

Con `COPILOT_PROVIDER=none`, o si el proveedor no responde, el Copilot contesta en modo **anclado**: solo
con las cifras que devolvieron las herramientas.

## Pruebas y calidad de código

```bash
cd quality && pytest && ruff check . && cd ..   # pipeline de calidad (Python)
npm --prefix backend test                        # API, Copilot y servidor MCP
npm --prefix frontend test                       # pantallas
```

El proyecto se desarrolla con TDD: en el historial cada cambio alterna commits `test(...) en rojo` y
`feat(...) (GREEN)`. GitHub Actions corre Ruff, pytest y Terraform en cada PR.

## Infraestructura y despliegue

Terraform vive en `infra/terraform/`: módulos reutilizables en `modules/` y una raíz por ambiente en
`envs/dev` y `envs/prod` (solo `prod` está aplicada). GitHub Actions se autentica con OIDC, sin llaves
estáticas. El procedimiento de despliegue y el diagnóstico están en [DEPLOY.md](DEPLOY.md) y el detalle de
los recursos en [infra/terraform/README.md](infra/terraform/README.md).

## Documentación

- [docs/portal-mp1.md](docs/portal-mp1.md): el portal de anotación del Proyecto 1 (antecedente).
- [docs/frente3-quality-api.md](docs/frente3-quality-api.md): endpoints `/quality/*`, contrato de artefactos y variables.
- [DEPLOY.md](DEPLOY.md): cómo publicar una versión en AWS y qué hacer cuando falla.
- [infra/terraform/README.md](infra/terraform/README.md): estructura de módulos y ambientes.
- Evidencia de la versión v1.0.0 (comandos, resultados y checksums): PR #29, en `docs/evidence/v1.0.0/` cuando se fusione.

## Si algo falla

| Síntoma | Causa y qué hacer |
|---|---|
| Las pantallas de calidad dicen «Sin datos» | Faltó `dvc pull -r prod` y `dvc repro` antes de `docker compose up`. O usa `make demo`. |
| `dvc pull` responde «no default remote» | Usa `dvc pull -r prod`: el repo no define un remoto por defecto. |
| `dvc pull` falla con credenciales inválidas | Renueva las credenciales de AWS. Sin acceso al bucket de PROD, usa `make demo`. |
| `dvc repro` termina con error en `release` | La compuerta quedó en `fail`. Lee la salida: dice qué check falló y con qué valor. |
| `make: command not found` (Windows) | Usa Git Bash o WSL, o corre a mano los comandos de [Arranque desde cero](#arranque-desde-cero). |
