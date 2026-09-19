# Evidencia de ejecución — Quality Gate v1.0.0

Evidencia reproducible de la corrida completa del pipeline de calidad
(Frente 2), ejecutada con `dvc repro` sobre el DAG real del proyecto
(`dvc.yaml`) contra el dataset real de 689 imágenes.

- **Commit de `main` utilizado:** `bc40d3b` — "style: fix import order and
  line length (ruff --fix + ruff format)"
- **Fecha de ejecución:** 2026-09-18
- **Dataset:** `data/annotations/coco-dataset.json` (689 imágenes),
  recuperado con `dvc pull -r prod` — mismo checksum que el ya publicado en
  PROD (ver sección 8)

## Estado real de DVC (sin ambigüedad)

- Los artefactos de `reports/` (image_hashes, analyzers, release,
  embeddings) que documenta este README **ya están publicados en el remoto
  `prod`** (`s3://proyecto2-prod-dvc-595981034933`) desde el corte de
  v1.0.0 hecho por Andrés. Esta corrida los **recuperó con `dvc pull -r
  prod`** y luego los **regeneró localmente con `dvc repro`**, confirmando
  que ambos coinciden (ver sección 8).
- **No se hizo ningún `dvc push`** en esta corrida: el usuario AWS usado
  (`proyecto2-prod-readonly`) es de solo lectura, verificado explícitamente
  (ver sección 8). No fue necesario, porque el objetivo era verificar
  reproducibilidad contra lo ya publicado, no publicar nada nuevo.
- Los JSON completos (`reports/*.json`) **no se suben a Git** — quedan
  versionados vía DVC (`dvc.lock` + los `.dvc` correspondientes). Este
  documento reúne los comandos ejecutados, sus resultados, y los checksums
  (`checksums.sha256`) de los artefactos reales y recuperables vía `dvc
  pull`, para que cualquier persona con acceso al remoto pueda verificar la
  integridad sin tener que regenerarlos.

## 1. Verificación previa (pytest, ruff)

```bash
cd quality
pytest -v
ruff check .
ruff format --check .
```

**Resultado:** 102/102 tests pasan en local. `ruff check` y `ruff format`
sin hallazgos (tras corregir orden de imports y longitud de línea en 4
archivos de `pipeline/` con `ruff check . --fix` y `ruff format .` —
solo reformateo, sin cambios de lógica).

## 2. `dvc repro` — primera corrida (regenera el pipeline)

```bash
dvc repro
```

**Resultado:**

```
'data/raw.dvc' didn't change, skipping
Running stage 'hash_images':
> PYTHONPATH=quality/src python pipeline/hash_images.py --images data/raw/images --out reports/image_hashes.json
pHash calculado para 689 imagenes (0 fallidas) -> reports/image_hashes.json
Updating lock file 'dvc.lock'

'data/annotations/coco-dataset.json.dvc' didn't change, skipping
Running stage 'analyze':
> PYTHONPATH=quality/src python pipeline/run_analyzers.py --coco data/annotations/coco-dataset.json --config quality/quality.yaml --hashes reports/image_hashes.json --out reports
5 reportes en reports/analyzers y resumen en reports/metrics.json
Updating lock file 'dvc.lock'

Stage 'embeddings' didn't change, skipping
Running stage 'release':
> PYTHONPATH=quality/src python pipeline/build_release.py --coco data/annotations/coco-dataset.json --config quality/quality.yaml --analyzers-dir reports/analyzers --out reports/release.json
release v0.0.0-dev -> reports/release.json
quality gate: pass (exit code 0)
  warn: duplicates {'group_count': 1, 'pair_count': 1}
splits: train=482, val=104, test=103 | fuga: ids=0 pares_cruzados=0
```

## 3. `dvc repro` — segunda corrida (confirma idempotencia)

```bash
dvc repro
```

**Resultado:**

```
'data/raw.dvc' didn't change, skipping
Stage 'hash_images' didn't change, skipping
'data/annotations/coco-dataset.json.dvc' didn't change, skipping
Stage 'analyze' didn't change, skipping
Stage 'embeddings' didn't change, skipping
Stage 'release' didn't change, skipping
Data and pipelines are up to date.
```

Confirma que el pipeline es determinista: sin cambios en las entradas, la
segunda corrida no vuelve a ejecutar ninguna etapa.

## 4. Verificación standalone del Quality Gate (CLI)

Además del pipeline por etapas (`dvc.yaml`), se verificó el comando
`quality-gate` expuesto como entrypoint del paquete, corrido directamente
sobre el mismo dataset (nota: usa `data/raw/coco.json`, copia local con el
mismo contenido que `data/annotations/coco-dataset.json` — ver checksum en
sección 8):

```bash
quality-gate \
  --coco data/raw/coco.json \
  --config quality/quality.yaml \
  --images-dir data/raw/images \
  --output evidence/quality_689.json
```

**Resultado:** `overall_status: "pass"`, `exit_code: 0` — mismo resultado
que el `reports/release.json` generado por el pipeline de `dvc.yaml`
(secciones 2–3), salvo `generated_at` y `dataset_version` (se le pasó
explícitamente `v1.0.0`, mientras que el pipeline por defecto usa
`v0.0.0-dev`).

## 5. Resultado del Quality Gate (6 checks)

| Check | Status | Severity | Observado |
|---|---|---|---|
| `min_images_per_class` | pass | fail | 2/2 clases alcanzan el umbral de 300 imágenes distintas |
| `invalid_boxes` | pass | fail | 0 cajas inválidas / 1455 anotaciones totales |
| `class_imbalance` | pass | warn | ratio 5.93 (umbral 10.0) |
| `duplicates` | warn | warn | 1 grupo, 1 par (imágenes 604 y 713, distancia pHash 0) |
| `small_objects` | pass (informativo) | warn | 0.41% de objetos pequeños |
| `spatial_bias` | pass (informativo) | warn | reportado, sin umbral bloqueante |

**`overall_status`: pass — `exit_code`: 0**

Ningún check con `severity: fail` fue violado, por lo que el release queda
aprobado según la regla confirmada por el PM (exit code ≠0 solo si algún
check violado tiene severity "fail").

## 6. Conteos de clases (antes/después de duplicados)

Incluidos en `class_counts` dentro de `reports/release.json`. Cubren M3 de
la rúbrica: mínimo 300 imágenes distintas en ≥2 clases, contadas antes y
después de colapsar el grupo de duplicados detectado (imágenes 604/713).

## 7. Splits — reproducibilidad y leakage

```
train = 482
val   = 104
test  = 103
fuga: ids=0, pares_cruzados=0
```

Cero leakage confirmado entre splits: ningún id de imagen aparece en más de
un split, y el grupo de duplicados detectado se mantiene junto en el mismo
split.

## 8. Verificación contra PROD (`dvc pull -r prod`)

Se configuró un perfil AWS de solo lectura (`proyecto2-prod-readonly`) y se
confirmó que efectivamente es de solo lectura antes de usarlo:

```bash
aws sts get-caller-identity --profile proyecto2-prod-readonly
# arn:aws:iam::595981034933:user/alejandra-proyecto2-dvc-readonly

echo "test" > /tmp/no-write.txt
aws s3 cp /tmp/no-write.txt \
  s3://proyecto2-prod-dvc-595981034933/no-write-alejandra.txt \
  --profile proyecto2-prod-readonly
# → falla con AccessDenied (confirmado)
```

Después se recuperaron los artefactos ya publicados en PROD:

```bash
dvc pull -r prod
```

**Dataset:** el checksum SHA-256 de `data/annotations/coco-dataset.json`
(recuperado de PROD) coincide exactamente con el usado en la corrida
standalone (`data/raw/coco.json`, sección 4):

```
93e9d6b8cd849241d149c55bdcaf7692a43fe64cbb3ded81116ce016bde3cdae
```

**Release:** se comparó el `release.json` recuperado de PROD contra el
generado localmente vía CLI standalone (sección 4). Ambos son idénticos
salvo `generated_at` y `dataset_version` (`v1.0.0` en la corrida local
explícita vs `v0.0.0-dev`, el valor que usa el pipeline por defecto). Todos
los checks del Quality Gate, conteos de clases y splits coinciden
exactamente tras normalizar ambos campos. Luego se corrió `dvc repro`
(secciones 2–3) para regenerar `reports/release.json` desde cero, con el
mismo contenido que el publicado en PROD salvo `generated_at`. Por eso el archivo
regenerado tiene otro checksum y **no** figura en `checksums.sha256` (ver la sección 10).

Esto confirma que el pipeline es reproducible: la corrida de Andrés al
cortar v1.0.0, la verificación standalone vía CLI, y la regeneración
completa vía `dvc repro`, producen el mismo resultado.

## 9. Prueba de mutación manual (Quality Gate)

Se invirtió temporalmente la comparación de `class_imbalance` en
`quality/src/dataset_quality/policy/quality_gate.py`
(`ratio > threshold` → `ratio < threshold`) para confirmar que la suite
detecta el cambio:

```bash
pytest tests/test_quality_gate.py -v
```

**Con la mutación:** `test_a_warn_severity_check_does_not_block_the_release`
falla (`assert 'pass' == 'warn'`) — confirma que el test protege
correctamente esa regla de negocio.

**Tras revertir** (`git diff` vacío): 7/7 tests pasan de nuevo.

## 10. Checksums

Ver `checksums.sha256` en este mismo directorio. Cubre los artefactos
reales del pipeline (`reports/`), recuperables por cualquier persona con
acceso de lectura al remoto `prod` vía `dvc pull -r prod` — no rutas
locales fuera del control de versiones.

`reports/release.json` **no está** en `checksums.sha256` a propósito: contiene
`generated_at`, así que cada regeneración produce un archivo con otro checksum, y el
que se regeneró en esta corrida no se publicó en PROD. El `release.json` publicado es el
que registra `dvc.lock` (md5 `3f07eec1c8be6866d307050da7d89308`, empujado por Andrés al
cortar v1.0.0) y es el que devuelve `dvc pull -r prod`. Además, `reports/metrics.json`
viene de git y no de `dvc pull`.

Verificación de integridad, después de `dvc pull -r prod`:

```bash
shasum -a 256 -c docs/evidence/v1.0.0/checksums.sha256
```

## 11. Artefactos verificados

| Artefacto | Ruta (recuperable vía `dvc pull`) |
|---|---|
| Dataset COCO | `data/annotations/coco-dataset.json` |
| Hashes pHash | `reports/image_hashes.json` |
| Reportes de analizadores | `reports/analyzers/*.json` |
| Resumen de analizadores | `reports/metrics.json` |
| Embeddings | `reports/embeddings.json` |
| Release completo | `reports/release.json` (md5 de `dvc.lock`; sin SHA-256, ver sección 10) |

Todos ya están respaldados en el remoto `prod` desde el corte de v1.0.0
(confirmado en la sección 8). No se requirió ningún `dvc push` adicional en
esta corrida.