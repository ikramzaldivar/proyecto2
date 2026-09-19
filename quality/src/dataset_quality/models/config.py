from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PIPELINE_VERSION_PATTERN = r"^v\d+\.\d+\.\d+(-[a-z0-9]+)?$"

# "warn" deja pasar el pipeline pero queda visible en el reporte; "fail"
# termina con exit code distinto de cero y bloquea el release (CAL 08).
Severity = Literal["warn", "fail"]

# Los 5 analizadores (CAL 03-07) más el mínimo de imágenes por clase (CAL 08)
# — quality.yaml SIEMPRE debe traer estos 6, o el pipeline no arranca.
REQUIRED_CHECKS = frozenset(
    {
        "min_images_per_class",
        "small_objects",
        "class_imbalance",
        "duplicates",
        "invalid_boxes",
        "spatial_bias",
    }
)


class CheckConfig(BaseModel):
    """Umbral y severidad de un check individual, tal como vive en quality.yaml.

    min_classes es opcional y solo aplica a min_images_per_class: el
    requisito real no es "300 imágenes en TODAS las clases" (eso haría
    fallar el gate por clases pequeñas como dog), sino "300 imágenes en al
    menos min_classes clases distintas"."""

    model_config = ConfigDict(extra="forbid")

    threshold: float
    severity: Severity
    min_classes: int | None = Field(default=None, ge=1)


class SplitConfig(BaseModel):
    """Proporciones y semilla para generar train/validation/test (CAL 09)."""

    model_config = ConfigDict(extra="forbid")

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


class QualityConfig(BaseModel):
    """quality.yaml completo: checks obligatorios + proporciones de splits.

    extra="forbid" en todos los niveles: un campo mal escrito en el YAML
    (ej. "serverity" en vez de "severity") debe rechazarse ruidosamente al
    cargar, no ignorarse en silencio.
    """

    model_config = ConfigDict(extra="forbid")

    checks: dict[str, CheckConfig]
    splits: SplitConfig

    @model_validator(mode="after")
    def check_required_checks_present(self) -> "QualityConfig":
        missing = REQUIRED_CHECKS - self.checks.keys()
        if missing:
            raise ValueError(f"missing required checks: {sorted(missing)}")
        return self


DEFAULT_DATASET_VERSION = "v0.0.0-dev"


class PipelineSettings(BaseSettings):
    """Variables de entorno del pipeline de release. Fail-fast: un valor
    inválido detiene el proceso con un mensaje claro, en vez de dejar
    que un DATASET_VERSION mal escrito llegue silenciosamente hasta
    release.json (ver CAL 00 — nada de leer os.environ suelto fuera de
    esta capa de configuración). Sin env_prefix: DATASET_VERSION ya se
    usa así en CI y dvc.yaml, y prefijarlo rompería esa integración."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dataset_version: str = Field(default=DEFAULT_DATASET_VERSION, pattern=PIPELINE_VERSION_PATTERN)
