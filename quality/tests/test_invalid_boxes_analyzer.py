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
            ],
        }
    )


def test_valid_box_is_not_flagged() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    invalid_ids = {box.annotation_id for box in report.invalid_boxes}
    assert VALID_ID not in invalid_ids


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


def test_reports_total_and_invalid_counts() -> None:
    report = analyze_invalid_boxes(_build_dataset(), CheckConfig(threshold=0, severity="fail"))
    assert report.total_annotations == 5
    assert report.invalid_count == 4  # todas menos VALID_ID
