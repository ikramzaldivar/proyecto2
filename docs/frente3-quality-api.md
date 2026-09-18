# Frente 3 — Contrato y API de calidad (Story A / APP 01)

Este documento es el acuerdo de handoff entre **Frente 2 (pipeline de
Alejandra)** y **Frente 3 (portal de Uriel)**. Define los artefactos que el
pipeline publica y los endpoints de solo lectura que el portal consume.

Mientras el pipeline real no publique los artefactos, el backend trabaja con
los **fixtures tipados** de `backend/tests/fixtures/quality/`. Al sustituirse
por los archivos reales, ninguna pantalla cambia: el contrato es el mismo.

## 1. Artefactos

El backend lee de un solo directorio (`QUALITY_ARTIFACTS_DIR`).

| Archivo | Lo produce | Contenido |
|---|---|---|
| `release.json` | Pipeline (Frente 2) | `quality` (gate), `analyzers` (5 reportes), `class_counts` (antes/después de duplicados), `splits` (+ `leakage`), `reannotation_queue`, `totals`, `categories`, `dataset_version` |
| `embeddings.json` | Pipeline / Frente 3 (APP 06) | Coordenadas 2D **precomputadas** (PCA) por imagen |
| `versions.json` | Proceso de release (Andrés / REL 02) | Timeline de versiones, estado DEV/PROD y métricas por versión |
| `quality.yaml` | Arquitectura de configuración (Frente 2) | Umbral y severidad por check (**Settings** lo edita en la Story B) |

Los esquemas Zod viven en `backend/src/logic/quality/contracts.ts` y son la
fuente única de verdad: si un artefacto no cumple, se rechaza con la ruta del
campo inválido.

## 2. Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `QUALITY_ARTIFACTS_DIR` | `../quality/output` | Directorio de artefactos |
| `QUALITY_CONFIG_PATH` | `../quality/quality.yaml` | Política editable desde Settings |

## 3. Endpoints (solo lectura)

Todos devuelven **200** con el JSON del contrato. Un artefacto ausente
devuelve **404** (`estado "sin datos"`); un artefacto que existe pero no
cumple el contrato devuelve **500** (`estado "error"`). No hay cifras
calculadas en el frontend ni valores de ejemplo.

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/quality/overview` | Totales, versión consultada y resumen del gate (`passCount` / `warnCount` / `failCount`, `overallStatus`, `exitCode`) |
| GET | `/quality/analyzers` | Los cinco reportes completos + `categories` (id → nombre) |
| GET | `/quality/splits` | Distribución por clase y split, `leakage`, `seed`, `class_counts` |
| GET | `/quality/reannotation-queue` | Muestras FAIL con `annotation_id`, `image_id`, `reason`, `analyzer`, `severity` |
| GET | `/quality/versions` | Timeline de versiones con estado DEV/PROD |
| GET | `/quality/versions/diff?from=&to=` | Imágenes/cajas añadidas, Δ small objects, clases que entran/salen del mínimo |
| GET | `/quality/settings` | `quality.yaml` como JSON (checks y splits) |
| PUT | `/quality/settings` | Valida y **escribe** `quality.yaml`; 400 si la política es inválida |
| GET | `/quality/embeddings` | Puntos PCA precomputados (APP 06) |

### Ejemplos

```bash
curl http://localhost:3100/quality/overview
curl "http://localhost:3100/quality/versions/diff?from=v1.0.0&to=v1.1.0"
curl http://localhost:3100/quality/analyzers
```

Estados de error:

```json
// 404 — sin datos
{ "error": "No hay release.json en \"...\". Ejecuta el pipeline de calidad para generarlo." }

// 404 — versión inexistente
{ "error": "La versión \"v9.9.9\" no existe en versions.json (disponibles: v1.0.0, v1.1.0)" }

// 400 — diff sin parámetros
{ "error": "Los parámetros \"from\" y \"to\" son obligatorios." }
```

## 4. Capas

```
data/artifacts/quality-artifact.repository.ts   ← lee archivos (único I/O)
logic/quality/contracts.ts                      ← Zod: valida el contrato
logic/quality/quality.service.ts                ← funciones PURAS (proyecciones y diffs)
logic/quality/quality-artifacts.service.ts      ← orquesta data + contracts + service
ui/quality.routes.ts                            ← HTTP; mapea NotFoundError→404
```

Las funciones de `quality.service.ts` no leen archivos, no leen el entorno y
no abren conexiones: se prueban con fixtures, igual que los analizadores de
Frente 2.

## 5. Regenerar los fixtures

Los fixtures actuales representan el contrato acordado. Cuando Frente 2
publique artefactos reales, basta con apuntar `QUALITY_ARTIFACTS_DIR` a su
directorio de salida; los fixtures se conservan solo para pruebas.

## 6. Vistas del portal (Story B)

Las seis vistas viven bajo rutas propias y consumen el API anterior. Ninguna
tiene cifras hardcodeadas: todas validan la respuesta con Zod y manejan
carga / error / sin datos.

| Ruta | Vista | Fuente |
|---|---|---|
| `/overview` | Resumen: totales, estado del gate y checks | `/quality/overview` |
| `/analyzers` | 5 pestañas con gráficas y muestras navegables | `/quality/analyzers` |
| `/splits` | Distribución por clase/split, fuga, seed y conteo antes/después | `/quality/splits` |
| `/versions` | Timeline DEV/PROD y diff entre versiones | `/quality/versions` |
| `/settings` | Edita y persiste `quality.yaml` | `/quality/settings` |
| `/copilot` | Vista del Copilot (su backend MCP es la story COP 01-02) | contrato de calidad |

## 7. Analítica exploratoria (APP 06)

`GET /quality/embeddings` sirve las coordenadas 2D **precomputadas offline**
(PCA). El portal **no** recalcula la reducción dimensional por request: pinta
los puntos ya calculados, previsualiza la imagen en hover/focus y filtra por
clase en el cliente.

Contrato de `embeddings.json` (lo produce el pipeline de calidad):

| Campo | Descripción |
|---|---|
| `method` | `pca` \| `tsne` \| `umap` |
| `explained_variance` | Varianza explicada por los 2 componentes |
| `points[]` | `image_id`, `file_name`, `x`, `y`, `category_ids`, `box_count` |

Regeneración: la precomputación corresponde al pipeline de calidad (Frente 2).
Hoy `main` **no** emite `embeddings.json`, así que el portal usa un fixture
tipado; el paso pendiente está listado en `docs/frente3-pendientes.md`.
