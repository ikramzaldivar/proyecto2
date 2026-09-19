# Contexto de build: la RAIZ del repo, no quality/.
#
#   docker build -f quality/Dockerfile -t proyecto2-quality .
#
# La imagen replica el arbol del repo (/app/quality y /app/pipeline) a proposito.
# tests/test_register_version_script.py ejecuta pipeline/register_version.py de
# verdad y lo localiza con rutas relativas al archivo de test. Si la imagen
# aplanara las carpetas, esas rutas apuntarian a la raiz del filesystem y las 7
# pruebas de ese archivo fallarian dentro del contenedor aunque pasen fuera.

FROM python:3.12-slim

WORKDIR /app

# Dependencias primero, en su propia capa: cambian mucho menos que el codigo,
# asi que el build no las reinstala en cada cambio de src o tests.
COPY quality/pyproject.toml quality/requirements.lock.txt ./quality/
RUN pip install --no-cache-dir -r quality/requirements.lock.txt

COPY quality/src/ ./quality/src/
RUN pip install --no-cache-dir --no-deps -e ./quality

COPY quality/tests/ ./quality/tests/
COPY quality/quality.yaml ./quality/quality.yaml

# Scripts de orquestacion del pipeline: viven en la raiz del repo, fuera del
# paquete, y el paquete no los importa — se ejecutan como procesos aparte.
COPY pipeline/ ./pipeline/

WORKDIR /app/quality

CMD ["pytest"]
