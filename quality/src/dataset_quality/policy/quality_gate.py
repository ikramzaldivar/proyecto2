from typing import Literal

from pydantic import BaseModel

from dataset_quality.analyzers.class_imbalance import ClassImbalanceReport
from dataset_quality.analyzers.duplicates import DuplicatesReport
from dataset_quality.analyzers.invalid_boxes import InvalidBoxesReport
from dataset_quality.analyzers.small_objects import SmallObjectsReport
from dataset_quality.analyzers.spatial_bias import SpatialBiasReport
from dataset_quality.models.config import QualityConfig, Severity

MAX_SAMPLES = 5

CheckStatus = Literal["pass", "warn", "fail"]


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    severity: Severity
    threshold: float
    observed: float
    samples: list[dict]


class QualityGateResult(BaseModel):
    checks: list[CheckResult]
    overall_status: Literal["pass", "fail"]
    exit_code: int


def _status_for(triggered: bool, severity: Severity) -> CheckStatus:
    return severity if triggered else "pass"


def evaluate_quality_gate(
    config: QualityConfig,
    small_objects: SmallObjectsReport,
    class_imbalance: ClassImbalanceReport,
    duplicates: DuplicatesReport,
    invalid_boxes: InvalidBoxesReport,
    spatial_bias: SpatialBiasReport,
) -> QualityGateResult:
    """Función pura (CAL 00): convierte los 5 reportes de analizadores +
    quality.yaml en una decisión reproducible PASS/WARN/FAIL, con exit code.

    Supuestos sobre qué DISPARA cada check (documentados aquí porque
    quality.yaml no define un "% máximo aceptable" distinto del umbral que
    cada analizador ya usa internamente — si la intención real es otra,
    ajustar aquí es un cambio acotado a esta función):

    - min_images_per_class: dispara si MENOS de min_classes categorías
      alcanzan el threshold de imágenes distintas.
    - invalid_boxes: dispara si hay AL MENOS 1 caja inválida.
    - class_imbalance: dispara si el ratio mayoría/minoría excede threshold.
    - duplicates: dispara si se encontró AL MENOS 1 grupo de duplicados.
    - small_objects y spatial_bias: informativos por ahora (nunca
      bloquean el release) — solo se reportan sus valores observados.
    """
    checks: list[CheckResult] = []

    min_config = config.checks["min_images_per_class"]
    classes_meeting_threshold = sum(
        1
        for distribution in class_imbalance.distributions
        if distribution.distinct_image_count >= min_config.threshold
    )
    min_classes = min_config.min_classes or 1
    checks.append(
        CheckResult(
            name="min_images_per_class",
            status=_status_for(classes_meeting_threshold < min_classes, min_config.severity),
            severity=min_config.severity,
            threshold=min_config.threshold,
            observed=classes_meeting_threshold,
            samples=[],
        )
    )

    invalid_config = config.checks["invalid_boxes"]
    checks.append(
        CheckResult(
            name="invalid_boxes",
            status=_status_for(invalid_boxes.invalid_count > 0, invalid_config.severity),
            severity=invalid_config.severity,
            threshold=invalid_config.threshold,
            observed=invalid_boxes.invalid_count,
            samples=[box.model_dump() for box in invalid_boxes.invalid_boxes[:MAX_SAMPLES]],
        )
    )

    imbalance_config = config.checks["class_imbalance"]
    ratio = class_imbalance.ratio or 0.0
    checks.append(
        CheckResult(
            name="class_imbalance",
            status=_status_for(ratio > imbalance_config.threshold, imbalance_config.severity),
            severity=imbalance_config.severity,
            threshold=imbalance_config.threshold,
            observed=ratio,
            samples=[],
        )
    )

    duplicates_config = config.checks["duplicates"]
    checks.append(
        CheckResult(
            name="duplicates",
            status=_status_for(len(duplicates.duplicate_groups) > 0, duplicates_config.severity),
            severity=duplicates_config.severity,
            threshold=duplicates_config.threshold,
            observed=len(duplicates.duplicate_groups),
            samples=[pair.model_dump() for pair in duplicates.pairs[:MAX_SAMPLES]],
        )
    )

    small_config = config.checks["small_objects"]
    checks.append(
        CheckResult(
            name="small_objects",
            status="pass",
            severity=small_config.severity,
            threshold=small_config.threshold,
            observed=small_objects.small_percent,
            samples=[
                sample.model_dump() for sample in small_objects.offending_samples[:MAX_SAMPLES]
            ],
        )
    )

    spatial_config = config.checks["spatial_bias"]
    checks.append(
        CheckResult(
            name="spatial_bias",
            status="pass",
            severity=spatial_config.severity,
            threshold=spatial_config.threshold,
            observed=spatial_bias.global_stats.std_x,
            samples=[],
        )
    )

    overall_status: Literal["pass", "fail"] = (
        "fail" if any(check.status == "fail" for check in checks) else "pass"
    )
    exit_code = 1 if overall_status == "fail" else 0

    return QualityGateResult(checks=checks, overall_status=overall_status, exit_code=exit_code)
