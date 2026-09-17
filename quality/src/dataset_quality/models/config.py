from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# "warn" deja pasar el pipeline pero queda visible en el reporte; "fail"
# termina con exit code distinto de cero y bloquea el release (CAL 08).
Severity = Literal["warn", "fail"]


class CheckConfig(BaseModel):
    """Umbral y severidad de un check individual, tal como vive en quality.yaml."""

    threshold: float
    severity: Severity


class QualityConfig(BaseModel):
    """quality.yaml completo: un CheckConfig por cada analizador, por nombre."""

    checks: dict[str, CheckConfig]


class SplitConfig(BaseModel):
    """Proporciones y semilla para generar train/validation/test (CAL 09)."""

    train: float = Field(gt=0, lt=1)
    val: float = Field(gt=0, lt=1)
    test: float = Field(gt=0, lt=1)
    seed: int = 42

    @model_validator(mode="after")
    def check_proportions_sum_to_one(self) -> "SplitConfig":
        total = self.train + self.val + self.test
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"train + val + test must sum to 1.0, got {total}")
        return self


class PipelineSettings(BaseSettings):
    """Variables de entorno del pipeline. Fail-fast: si falta una variable
    requerida, el proceso no arranca — nada de leer os.environ suelto
    dentro de los analizadores (ver CAL 00)."""

    model_config = SettingsConfigDict(env_prefix="DATASET_QUALITY_")

    coco_source_path: str
