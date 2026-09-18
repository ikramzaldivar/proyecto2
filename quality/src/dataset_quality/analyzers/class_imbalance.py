from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig, Severity


class ClassDistribution(BaseModel):
    category_id: int
    distinct_image_count: int
    box_count: int


class ClassImbalanceReport(BaseModel):
    threshold: float
    severity: Severity
    distributions: list[ClassDistribution]
    majority_category_id: int | None
    minority_category_id: int | None
    ratio: float | None
    classes_below_min_images: list[int]


def analyze_class_imbalance(
    dataset: CocoDataset, config: CheckConfig, min_images_threshold: int
) -> ClassImbalanceReport:
    """Función pura (CAL 00). Cuenta, por categoría, imágenes DISTINTAS y
    cajas por separado — nunca se confunden entre sí (el requisito real
    de la rúbrica es sobre imágenes distintas, no sobre cajas)."""
    box_counts: dict[int, int] = {}
    images_by_category: dict[int, set[int]] = {}

    for annotation in dataset.annotations:
        box_counts[annotation.category_id] = box_counts.get(annotation.category_id, 0) + 1
        images_by_category.setdefault(annotation.category_id, set()).add(annotation.image_id)

    distributions = [
        ClassDistribution(
            category_id=category.id,
            distinct_image_count=len(images_by_category.get(category.id, set())),
            box_count=box_counts.get(category.id, 0),
        )
        for category in dataset.categories
    ]

    counts_by_category = {
        distribution.category_id: distribution.distinct_image_count
        for distribution in distributions
    }

    # El ratio mayoría/minoría solo tiene sentido entre categorías que sí
    # tienen al menos 1 imagen — una categoría con 0 imágenes no es una
    # "minoría", es un caso aparte (y de todos modos cae en
    # classes_below_min_images).
    nonzero_counts = {
        category_id: count for category_id, count in counts_by_category.items() if count > 0
    }

    if nonzero_counts:
        majority_id = max(nonzero_counts, key=lambda cid: nonzero_counts[cid])
        minority_id = min(nonzero_counts, key=lambda cid: nonzero_counts[cid])
        ratio = counts_by_category[majority_id] / counts_by_category[minority_id]
    else:
        majority_id = None
        minority_id = None
        ratio = None

    classes_below_min_images = [
        category_id
        for category_id, count in counts_by_category.items()
        if count < min_images_threshold
    ]

    return ClassImbalanceReport(
        threshold=config.threshold,
        severity=config.severity,
        distributions=distributions,
        majority_category_id=majority_id,
        minority_category_id=minority_id,
        ratio=ratio,
        classes_below_min_images=classes_below_min_images,
    )
