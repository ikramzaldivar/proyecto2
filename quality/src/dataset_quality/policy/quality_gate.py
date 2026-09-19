import math
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
    observed: dict
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

    Reglas confirmadas por el PM (no reinterpretar el threshold de cada
    check con otro significado que el que ya tiene en su analizador):

    - min_images_per_class: viola si MENOS de min_classes categorías
      alcanzan threshold imágenes distintas.
    - invalid_boxes: viola si existe AL MENOS 1 caja inválida. severity
      decide si eso es warn o fail.
    - class_imbalance: viola si el ratio mayoría/minoría es ESTRICTAMENTE
      MAYOR al threshold.
    - duplicates: viola si existe AL MENOS 1 grupo de duplicados. El
      threshold de este check sigue siendo la distancia pHash usada por el
      analizador para decidir qué es "duplicado" — NUNCA se reutiliza aquí
      como cantidad máxima de grupos permitidos.
    - small_objects: NO bloqueante (severity: warn fijo en quality.yaml).
      Su threshold es el tamaño en px para considerar un objeto "pequeño",
      NO un porcentaje máximo — no se reutiliza como tal. Reporta
      small_percent, resultados por categoría y muestras.
    - spatial_bias: NO bloqueante. Reporta todas sus estadísticas
      (global y por categoría), sin un umbral de "demasiado sesgo" todavía.

    El exit code es distinto de cero únicamente si algún check violado
    tiene severity "fail" — los "warn" aparecen en el reporte pero nunca
    bloquean el release.
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
            observed={
                "classes_meeting_threshold": classes_meeting_threshold,
                "min_classes_required": min_classes,
            },
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
            observed={
                "invalid_count": invalid_boxes.invalid_count,
                "total_annotations": invalid_boxes.total_annotations,
            },
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
            observed={
                "ratio": ratio,
                "majority_category_id": class_imbalance.majority_category_id,
                "minority_category_id": class_imbalance.minority_category_id,
            },
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
            observed={
                "group_count": len(duplicates.duplicate_groups),
                "pair_count": len(duplicates.pairs),
            },
            samples=[pair.model_dump() for pair in duplicates.pairs[:MAX_SAMPLES]],
        )
    )

    small_config = config.checks["small_objects"]
    small_objects_triggered = (
        small_config.max_small_percent is not None
        and small_objects.small_percent > small_config.max_small_percent
    )
    checks.append(
        CheckResult(
            name="small_objects",
            status=_status_for(small_objects_triggered, small_config.severity),
            severity=small_config.severity,
            threshold=small_config.threshold,
            observed={
                "small_percent": small_objects.small_percent,
                "percent_by_category": small_objects.percent_by_category,
                "most_affected_category_id": small_objects.most_affected_category_id,
                "max_small_percent": small_config.max_small_percent,
            },
            samples=[
                sample.model_dump() for sample in small_objects.offending_samples[:MAX_SAMPLES]
            ],
        )
    )

    spatial_config = config.checks["spatial_bias"]
    center_deviation = math.sqrt(
        (spatial_bias.global_stats.mean_x - 0.5) ** 2
        + (spatial_bias.global_stats.mean_y - 0.5) ** 2
    )
    spatial_bias_triggered = (
        spatial_config.max_center_deviation is not None
        and center_deviation > spatial_config.max_center_deviation
    )
    checks.append(
        CheckResult(
            name="spatial_bias",
            status=_status_for(spatial_bias_triggered, spatial_config.severity),
            severity=spatial_config.severity,
            threshold=spatial_config.threshold,
            observed={
                "global_stats": spatial_bias.global_stats.model_dump(),
                "stats_by_category": {
                    str(category_id): stats.model_dump()
                    for category_id, stats in spatial_bias.stats_by_category.items()
                },
                "center_deviation": center_deviation,
                "max_center_deviation": spatial_config.max_center_deviation,
            },
            samples=[],
        )
    )

    overall_status: Literal["pass", "fail"] = (
        "fail" if any(check.status == "fail" for check in checks) else "pass"
    )
    exit_code = 1 if overall_status == "fail" else 0

    return QualityGateResult(checks=checks, overall_status=overall_status, exit_code=exit_code)
