#!/usr/bin/env bash
# Publica un release APROBADO en el bucket inmutable (S3 con Object Lock).
#
# Esto es ORQUESTACION: no decide nada de calidad. Solo comprueba que lo que
# hay en disco es un release valido con la etiqueta pedida, arma un manifiesto
# con hashes y lo sube a s3://<bucket>/<version>/. El bucket tiene Object Lock
# (modo GOVERNANCE, retencion por defecto en Terraform): lo publicado no se
# puede borrar ni sobrescribir durante la retencion, ni por accidente.
#
# Se corre a mano, DESPUES de register_version.py y de `dvc push -r prod`,
# desde la raiz del repo y con credenciales temporales de AWS en el entorno:
#
#     export AWS_PROFILE=<perfil>
#     pipeline/publish_release.sh v1.0.0
#
# Que se publica (todo lo necesario para auditar el release sin DVC):
#   release.json      el release completo (gate, splits, fuga, colas)
#   metrics.json      metricas resumidas
#   versions.json     historial de versiones tal como quedo al publicar
#   quality.yaml      la politica con la que se evaluo
#   dvc.lock          hashes de cada etapa y salida
#   coco-dataset.json las anotaciones
#   manifest.json     sha256 de lo anterior + commit + hash DVC + fecha
# Las imagenes NO se copian: viven en el remoto DVC y su hash va en el manifiesto.
#
# Nunca sobrescribe: si el prefijo <version>/ ya existe, aborta. Un release
# corregido es una version nueva.

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "uso: pipeline/publish_release.sh vMAYOR.MENOR.PARCHE" >&2
  exit 2
fi
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: '$VERSION' no es una version semantica (ej. v1.2.0)" >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

RELEASE=reports/release.json
FILES=(
  reports/release.json
  reports/metrics.json
  reports/versions.json
  quality/quality.yaml
  dvc.lock
  data/annotations/coco-dataset.json
)

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { echo "error: falta $f (haz dvc pull -r prod)" >&2; exit 1; }
done

# --- 1. El release en disco debe ser el que se pide y debe haber pasado la compuerta.
read -r RELEASE_VERSION STATUS < <(python3 -c '
import json, sys
r = json.load(open(sys.argv[1]))
print(r["dataset_version"], r["quality"]["overall_status"])
' "$RELEASE")

if [[ "$RELEASE_VERSION" != "$VERSION" ]]; then
  echo "error: release.json dice dataset_version=$RELEASE_VERSION, no $VERSION." >&2
  echo "       Re-corta la etapa: DATASET_VERSION=$VERSION dvc repro -f -s release" >&2
  exit 1
fi
if [[ "$STATUS" != "pass" ]]; then
  echo "error: la compuerta quedo en '$STATUS'. Un release bloqueado no se publica." >&2
  exit 1
fi
if ! python3 -c '
import json, sys
v = json.load(open("reports/versions.json"))["versions"]
sys.exit(0 if any(e["version"] == sys.argv[1] for e in v) else 1)
' "$VERSION"; then
  echo "error: $VERSION no esta en reports/versions.json. Corre register_version.py primero." >&2
  exit 1
fi

# --- 2. Destino.
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="${RELEASES_BUCKET:-proyecto2-prod-releases-$ACCOUNT}"
PREFIX="s3://$BUCKET/$VERSION/"

if aws s3api head-object --bucket "$BUCKET" --key "$VERSION/release.json" >/dev/null 2>&1; then
  echo "error: $PREFIX ya existe. Un release publicado no se sobrescribe; corta una version nueva." >&2
  exit 1
fi

# --- 3. Manifiesto.
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }

COMMIT=$(git rev-parse --short HEAD)
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
DVC_REVISION=$(python3 -c '
import yaml; d = yaml.safe_load(open("data/raw.dvc")); print(d["outs"][0]["md5"].removesuffix(".dir"))
' 2>/dev/null || echo "")

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
{
  echo "{"
  echo "  \"version\": \"$VERSION\","
  echo "  \"published_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"commit\": \"$COMMIT\","
  echo "  \"working_tree_clean\": $([[ "$DIRTY" == "0" ]] && echo true || echo false),"
  echo "  \"dvc_revision\": \"$DVC_REVISION\","
  echo "  \"bucket\": \"$BUCKET\","
  echo "  \"files\": {"
  n=${#FILES[@]}; i=0
  for f in "${FILES[@]}"; do
    i=$((i+1)); sep=$([[ $i -lt $n ]] && echo "," || echo "")
    echo "    \"$(basename "$f")\": {\"source\": \"$f\", \"sha256\": \"$(sha256 "$f")\", \"bytes\": $(wc -c < "$f" | tr -d ' ')}$sep"
  done
  echo "  }"
  echo "}"
} > "$STAGE/manifest.json"
python3 -m json.tool "$STAGE/manifest.json" >/dev/null   # valida que sea JSON

echo "Publicando $VERSION en $PREFIX (commit $COMMIT, arbol $([[ "$DIRTY" == "0" ]] && echo limpio || echo "CON CAMBIOS SIN COMMIT"))"

# --- 4. Subida. Object Lock exige Content-MD5; la CLI lo manda sola.
for f in "${FILES[@]}"; do
  aws s3 cp --only-show-errors "$f" "$PREFIX$(basename "$f")"
done
aws s3 cp --only-show-errors "$STAGE/manifest.json" "${PREFIX}manifest.json"

# --- 5. Verificacion: todo esta y esta bajo retencion.
echo
aws s3 ls "$PREFIX"
echo
aws s3api get-object-retention --bucket "$BUCKET" --key "$VERSION/release.json" \
  --query 'Retention.[Mode,RetainUntilDate]' --output text | awk '{print "Object Lock:", $1, "hasta", $2}'
echo "Listo. Verifica con: aws s3 cp ${PREFIX}manifest.json - | python3 -m json.tool"
