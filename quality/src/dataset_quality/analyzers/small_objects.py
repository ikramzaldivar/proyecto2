from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig, Severity


class OffendingSample(BaseModel):
    annotation_id: int
    image_id: int
    category_id: int
    width: float
    height: float


class SmallObjectsReport(BaseModel):
    threshold_px: float
    severity: Severity
    total_annotations: int
    small_count: int
    small_percent: float
    percent_by_category: dict[int, float]
    most_affected_category_id: int | None
    offending_samples: list[OffendingSample]


def analyze_small_objects(dataset: CocoDataset, config: CheckConfig) -> SmallObjectsReport:
    """Función pura (CAL 00): no toca disco, red ni entorno — solo recibe
    datos y configuración, y devuelve un reporte. Un objeto se considera
    "pequeño" si su área (width * height) es menor al umbral al cuadrado
    (ej. 32px -> área mínima de referencia 1024px²), la misma definición
    que usa COCO."""
    threshold_area = config.threshold**2
    total = len(dataset.annotations)

    small_annotations = [
        annotation
        for annotation in dataset.annotations
        if (annotation.bbox[2] * annotation.bbox[3]) < threshold_area
    ]
    small_count = len(small_annotations)
    small_percent = (small_count / total * 100) if total else 0.0

    totals_by_category: dict[int, int] = {}
    small_by_category: dict[int, int] = {}
    for annotation in dataset.annotations:
        totals_by_category[annotation.category_id] = (
            totals_by_category.get(annotation.category_id, 0) + 1
        )
    for annotation in small_annotations:
        small_by_category[annotation.category_id] = (
            small_by_category.get(annotation.category_id, 0) + 1
        )

    percent_by_category = {
        category_id: (small_by_category.get(category_id, 0) / category_total * 100)
        for category_id, category_total in totals_by_category.items()
    }

    most_affected_category_id = (
        max(percent_by_category, key=lambda category_id: percent_by_category[category_id])
        if percent_by_category
        else None
    )

    offending_samples = [
        OffendingSample(
            annotation_id=annotation.id,
            image_id=annotation.image_id,
            category_id=annotation.category_id,
            width=annotation.bbox[2],
            height=annotation.bbox[3],
        )
        for annotation in small_annotations
    ]

    return SmallObjectsReport(
        threshold_px=config.threshold,
        severity=config.severity,
        total_annotations=total,
        small_count=small_count,
        small_percent=small_percent,
        percent_by_category=percent_by_category,
        most_affected_category_id=most_affected_category_id,
        offending_samples=offending_samples,
    )
