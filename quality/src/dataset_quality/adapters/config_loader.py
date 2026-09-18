from pathlib import Path

import yaml

from dataset_quality.models.config import QualityConfig


def load_quality_config(path: Path) -> QualityConfig:
    """Lee y valida quality.yaml. Falla ruidosamente si el archivo no existe
    o si su contenido no cumple el esquema (ver models/config.py)."""
    if not path.exists():
        raise FileNotFoundError(f"quality config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    return QualityConfig.model_validate(raw)
