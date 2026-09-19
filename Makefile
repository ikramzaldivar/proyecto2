# Arranque del proyecto. Cada objetivo es solo una secuencia de los comandos que
# el README documenta paso a paso ("Arranque desde cero"): si no tienes make,
# corre esos mismos comandos a mano.
#
#   make setup   instala las dependencias (una sola vez)
#   make up      dvc pull -> dvc repro -> docker compose up --build
#   make demo    lo mismo con un dataset sintetico, sin acceso a los remotos de DVC
#   make down    apaga los contenedores
#
# Portabilidad: `setup` y `demo` solo usan Python, npm, pip y docker, y pasan las
# variables con `export` de make, que se aplica igual en sh, cmd y PowerShell. `up`
# corre `dvc repro`, y las etapas de dvc.yaml usan `PYTHONPATH=... python`, que
# necesita un shell POSIX (Linux, macOS, WSL o Git Bash en Windows).

.PHONY: setup up demo down

DEMO_DIR = demo
DEMO_POLICY = quality/quality.demo.yaml

# .env se crea con Python: `cp -n` no existe en Windows, y copyfile copia los bytes
# exactos (el .env.example lleva acentos; read_text/write_text los pasaria por la
# codificacion local, que en Windows no es UTF-8). Nunca pisa un .env existente.
setup:
	python -c "import pathlib, shutil; pathlib.Path('.env').exists() or shutil.copyfile('.env.example', '.env')"
	pip install -e "quality/[dev]"
	pip install "dvc[s3]"
	npm --prefix backend ci
	npm --prefix frontend ci

# Los artefactos que lee el portal (release.json, embeddings.json...) son salidas
# del pipeline y no van en git: hay que traer los datos y regenerarlos ANTES de
# levantar la app, o las seis pantallas de calidad arrancan vacias.
up:
	dvc pull -r prod
	dvc repro
	docker compose up --build

# Dataset sintetico en demo/ (ignorado por git). No usa DVC ni la politica real:
# la politica de la demo es quality/quality.demo.yaml (SOLO DEMO). Las carpetas de
# salida las crean los propios scripts. Se usa `export` y no el prefijo VAR=valor,
# que solo existe en shells POSIX.
demo: export PYTHONPATH = quality/src
demo: export QUALITY_REPORTS_DIR = ./$(DEMO_DIR)/reports
demo: export QUALITY_CONFIG_FILE = ./$(DEMO_POLICY)
demo:
	python pipeline/make_demo_dataset.py --out $(DEMO_DIR)
	python pipeline/hash_images.py --images $(DEMO_DIR)/images --out $(DEMO_DIR)/reports/image_hashes.json
	python pipeline/run_analyzers.py --coco $(DEMO_DIR)/coco.json --config $(DEMO_POLICY) --hashes $(DEMO_DIR)/reports/image_hashes.json --out $(DEMO_DIR)/reports
	python pipeline/build_release.py --coco $(DEMO_DIR)/coco.json --config $(DEMO_POLICY) --analyzers-dir $(DEMO_DIR)/reports/analyzers --out $(DEMO_DIR)/reports/release.json --dataset-version v0.1.0-demo
	cd backend && npm run --silent embeddings -- --coco ../$(DEMO_DIR)/coco.json --output ../$(DEMO_DIR)/reports/embeddings.json --generated-at 1970-01-01T00:00:00Z
	python pipeline/register_version.py --release $(DEMO_DIR)/reports/release.json --config $(DEMO_POLICY) --registry $(DEMO_DIR)/reports/versions.json --version v0.1.0 --dvc-revision demo-sintetico
	docker compose up --build

down:
	docker compose down
