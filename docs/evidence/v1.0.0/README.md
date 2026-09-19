# Evidencia de ejecución — Quality Gate v1.0.0

Evidencia reproducible de la corrida completa del pipeline de calidad
(Frente 2) contra el dataset real de 689 imágenes provisto por el PM.

- **Commit de `main` utilizado:** `bc40d3b` — "style: fix import order and
  line length (ruff --fix + ruff format)"
- **Fecha de ejecución:** 2026-09-18
- **Dataset:** `data/raw/` (689 imágenes, `data/raw/coco.json`)

Los JSON completos generados por cada comando (hashes, reportes de
analizadores, `release.json`) están versionados con DVC y respaldados en los
remotos DEV y PROD — **no se suben a Git directamente**, ya que son
artefactos del pipeline. Este documento reúne los comandos ejecutados y sus
resultados, junto con los checksums (`checksums.sha256`) para verificar la
integridad de cada artefacto sin necesidad de regenerarlo.

> **Pendiente:** el `dvc push` a los remotos DEV y PROD, y la confirmación
> del segundo `dvc repro`, están sujetos al setup de DVC que administra
> Andrés (no había `dvc` instalado ni documentado en este entorno al momento
> de esta corrida). Se actualizará este README en cuanto se confirme el push
> y la salida de `dvc repro`.

## 1. Verificación previa (pytest, ruff)

\`\`\`bash
cd quality
pytest -v
ruff check .
ruff format --check .
\`\`\`

**Resultado:** 102/102 tests pasan en local. `ruff check` y `ruff format`
sin hallazgos (tras corregir orden de imports y longitud de línea en 4
archivos de `pipeline/` con `ruff check . --fix` y `ruff format .` —
solo reformateo, sin cambios de lógica).

## 2. Pipeline completo contra el dataset real (689 imágenes)

### Etapa 1 — pHash de las imágenes

\`\`\`bash
python pipeline/hash_images.py \
  --images data/raw/images \
  --out evidence/hashes_689.json
\`\`\`

**Resultado:** `pHash calculado para 689 imagenes (0 fallidas) -> evidence/hashes_689.json`

### Etapa 2 — Analizadores

\`\`\`bash
python pipeline/run_analyzers.py \
  --coco data/raw/coco.json \
  --config quality/quality.yaml \
  --hashes evidence/hashes_689.json \
  --out evidence/analyzers_689
\`\`\`

**Resultado:** `5 reportes en evidence/analyzers_689/analyzers y resumen en evidence/analyzers_689/metrics.json`

### Etapa 3 — Release (Quality Gate + conteos + splits)

\`\`\`bash
python pipeline/build_release.py \
  --coco data/raw/coco.json \
  --config quality/quality.yaml \
  --analyzers-dir evidence/analyzers_689/analyzers \
  --out evidence/release_689.json \
  --dataset-version v1.0.0
\`\`\`

**Resultado:**

\`\`\`
release v1.0.0 -> evidence/release_689.json
quality gate: pass (exit code 0)
  warn: duplicates {'group_count': 1, 'pair_count': 1}
splits: train=482, val=104, test=103 | fuga: ids=0 pares_cruzados=0
\`\`\`

## 3. Resultado del Quality Gate (6 checks)

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

## 4. Conteos de clases (antes/después de duplicados)

Incluidos en `class_counts` dentro de `evidence/release_689.json`. Cubren
M3 de la rúbrica: mínimo 300 imágenes distintas en ≥2 clases, contadas antes
y después de colapsar el grupo de duplicados detectado (imágenes 604/713).

## 5. Splits — reproducibilidad y leakage

\`\`\`
train = 482
val   = 104
test  = 103
fuga: ids=0, pares_cruzados=0
\`\`\`

Cero leakage confirmado entre splits: ningún id de imagen aparece en más de
un split, y el grupo de duplicados detectado se mantiene junto en el mismo
split.

## 6. Prueba de mutación manual (Quality Gate)

Se invirtió temporalmente la comparación de `class_imbalance` en
`quality/src/dataset_quality/policy/quality_gate.py`
(`ratio > threshold` → `ratio < threshold`) para confirmar que la suite
detecta el cambio:

\`\`\`bash
pytest tests/test_quality_gate.py -v
\`\`\`

**Con la mutación:** `test_a_warn_severity_check_does_not_block_the_release`
falla (`assert 'pass' == 'warn'`) — confirma que el test protege
correctamente esa regla de negocio.

**Tras revertir** (`git diff` vacío): 7/7 tests pasan de nuevo.

## 7. Checksums

Ver `checksums.sha256` en este mismo directorio. Verificación de integridad:

\`\`\`bash
shasum -a 256 -c docs/evidence/v1.0.0/checksums.sha256
\`\`\`

## 8. Artefactos (vía DVC, no en Git)

| Artefacto | Ruta |
|---|---|
| Hashes pHash | `evidence/hashes_689.json` |
| Quality Gate standalone | `evidence/quality_689.json` |
| Release completo | `evidence/release_689.json` |
| Reportes de analizadores | `evidence/analyzers_689/analyzers/*.json` |
| Resumen de analizadores | `evidence/analyzers_689/metrics.json` |

Rutas compartidas con Andrés para publicar el release aprobado en el bucket
inmutable de S3.