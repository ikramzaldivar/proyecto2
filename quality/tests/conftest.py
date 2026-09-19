import sys
from pathlib import Path

# pipeline/ no es un paquete instalable: contiene los scripts de orquestacion y la
# demo sintetica (pipeline/demo/). Los tests que la usan lo importan desde aqui.
PIPELINE_DIR = Path(__file__).resolve().parents[2] / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))
