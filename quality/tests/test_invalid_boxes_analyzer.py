from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig

CATEGORY_ID = 1
IMAGE_ID = 1  # imagen de 100x100

VALID_ID = 1
NEGATIVE_COORDS_ID = 2
OUT_OF_BOUNDS_ID = 3
ZERO_SIZE_ID = 4
AREA_MISMATCH_ID = 5
NEGATIVE_WIDTH_ID = 6


def _annotation(annotation_id: int, bbox: list[float], area: float) -> dict:
    return {
        "id": annotation_id,
        "image_id": IMAGE_ID,
        "category_id": CATEGORY_ID,
        "bbox": bbox,
        "area": area,
        "iscrowd": 0,
    }


def _build_dataset() -> CocoDataset:
    return CocoDataset.model_validate(
        {
            "images": [{"id": IMAGE_ID, "file_name": "a.jpg", "width": 100, "height": 100}],
            "categories": [{"id": CATEGORY_ID, "name": "car"}],
            "annotations": [
                _annotation(VALID_ID, [10, 10, 20, 20], 400),
                # CAL 06, criterio de cierre: "una caja negativa"
                _annotation(NEGATIVE_COORDS_ID, [-5, 10, 20, 20], 400),
                # CAL 06, criterio de cierre: "otra que exceda la imagen"
                _annotation(OUT_OF_BOUNDS_ID, [90, 90, 20, 20], 400),
                _annotation(ZERO_SIZE_ID, [10, 10, 0, 20], 0),
                _annotation(AREA_MISMATCH_ID, [10, 10, 20, 20], 999),
                # El prompt pide explícitamente ancho NEGATIVO, distinto de
                # ancho cero (ZERO_SIZE_ID ya cubre el caso de cero).
                _annotation(NEGATIVE_WIDTH_ID, [10, 10, -5, 20], 400),
            ],
        }
    )


def test_valid_box_is_not_flagged() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    invalid_ids = {box.annotation_id for box in report.invalid_boxes}
    assert VALID_ID not in invalid_ids


def test_box_touching_the_border_with_float_rounding_is_not_a_false_positive() -> None:
    # Reportado por el PM: x + width puede dar un poco más de image.width
    # solo por imprecisión de punto flotante (ej. 33.333333333333336 +
    # 66.66666666666667 = 100.00000000000001 en Python), sin que la caja
    # realmente se salga de la imagen. No debe marcarse out_of_bounds.
    dataset = CocoDataset.model_validate(
        {
            "images": [{"id": IMAGE_ID, "file_name": "a.jpg", "width": 100, "height": 100}],
            "categories": [{"id": CATEGORY_ID, "name": "car"}],
            "annotations": [
                _annotation(
                    99,
                    [33.333333333333336, 0, 66.66666666666667, 20],
                    66.66666666666667 * 20,
                )
            ],
        }
    )
    report = analyze_invalid_boxes(dataset, CheckConfig(threshold=0, severity="fail"))
    box = next((b for b in report.invalid_boxes if b.annotation_id == 99), None)
    assert box is None


def test_flags_negative_coordinates_with_the_right_reason() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    box = next(b for b in report.invalid_boxes if b.annotation_id == NEGATIVE_COORDS_ID)
    assert "negative_coordinates" in box.reasons


def test_flags_out_of_bounds_box_with_the_right_reason() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    box = next(b for b in report.invalid_boxes if b.annotation_id == OUT_OF_BOUNDS_ID)
    assert "out_of_bounds" in box.reasons


def test_flags_zero_size_box_with_the_right_reason() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    box = next(b for b in report.invalid_boxes if b.annotation_id == ZERO_SIZE_ID)
    assert "zero_or_negative_size" in box.reasons


def test_flags_area_mismatch_with_the_right_reason() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    box = next(b for b in report.invalid_boxes if b.annotation_id == AREA_MISMATCH_ID)
    assert "area_mismatch" in box.reasons


def test_flags_negative_width_with_the_right_reason() -> None:
    # Caso pedido explícitamente por el prompt: ancho negativo, distinto
    # del caso de ancho cero (test_flags_zero_size_box_with_the_right_reason).
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    box = next(b for b in report.invalid_boxes if b.annotation_id == NEGATIVE_WIDTH_ID)
    assert "zero_or_negative_size" in box.reasons


def test_reports_total_and_invalid_counts() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    assert report.total_annotations == 6
    assert report.invalid_count == 5  # todas menos VALID_ID
