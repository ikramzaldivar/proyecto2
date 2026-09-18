from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig, Severity


class InvalidBox(BaseModel):
    annotation_id: int
    image_id: int
    bbox: list[float]
    reasons: list[str]


class InvalidBoxesReport(BaseModel):
    threshold: float
    severity: Severity
    total_annotations: int
    invalid_count: int
    invalid_boxes: list[InvalidBox]


def analyze_invalid_boxes(dataset: CocoDataset, config: CheckConfig) -> InvalidBoxesReport:
    """Función pura (CAL 00). CocoAnnotation (CAL 01) solo valida que bbox
    tenga 4 elementos — no valida que los VALORES sean sensatos dado el
    tamaño real de la imagen. Eso es justo lo que revisa este analizador,
    con 4 reglas independientes (una caja puede violar varias a la vez)."""
    images_by_id = {image.id: image for image in dataset.images}
    invalid_boxes: list[InvalidBox] = []

    for annotation in dataset.annotations:
        x, y, width, height = annotation.bbox
        reasons: list[str] = []

        if width <= 0 or height <= 0:
            reasons.append("zero_or_negative_size")

        if x < 0 or y < 0:
            reasons.append("negative_coordinates")

        image = images_by_id.get(annotation.image_id)
        if image is not None and (x + width > image.width or y + height > image.height):
            reasons.append("out_of_bounds")

        expected_area = width * height
        if abs(annotation.area - expected_area) > 1e-6:
            reasons.append("area_mismatch")

        if reasons:
            invalid_boxes.append(
                InvalidBox(
                    annotation_id=annotation.id,
                    image_id=annotation.image_id,
                    bbox=annotation.bbox,
                    reasons=reasons,
                )
            )

    return InvalidBoxesReport(
        threshold=config.threshold,
        severity=config.severity,
        total_annotations=len(dataset.annotations),
        invalid_count=len(invalid_boxes),
        invalid_boxes=invalid_boxes,
    )
