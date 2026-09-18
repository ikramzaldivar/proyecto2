from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig
from dataset_quality.policy.reannotation_queue import build_reannotation_queue

CATEGORY_ID = 1
IMAGE_ID = 1


def _dataset_with_invalid_box() -> CocoDataset:
    return CocoDataset.model_validate(
        {
            "images": [{"id": IMAGE_ID, "file_name": "a.jpg", "width": 100, "height": 100}],
            "categories": [{"id": CATEGORY_ID, "name": "car"}],
            "annotations": [
                {
                    "id": 1,
                    "image_id": IMAGE_ID,
                    "category_id": CATEGORY_ID,
                    "bbox": [-5, 10, 20, 20],  # coordenada negativa -> inválida
                    "area": 400,
                    "iscrowd": 0,
                }
            ],
        }
    )


def _dataset_with_corrected_box() -> CocoDataset:
    # Misma anotación (id=1), pero ya corregida.
    return CocoDataset.model_validate(
        {
            "images": [{"id": IMAGE_ID, "file_name": "a.jpg", "width": 100, "height": 100}],
            "categories": [{"id": CATEGORY_ID, "name": "car"}],
            "annotations": [
                {
                    "id": 1,
                    "image_id": IMAGE_ID,
                    "category_id": CATEGORY_ID,
                    "bbox": [5, 10, 20, 20],  # ya sin coordenada negativa
                    "area": 400,
                    "iscrowd": 0,
                }
            ],
        }
    )


def _config() -> CheckConfig:
    return CheckConfig(threshold=0, severity="fail")


def test_invalid_box_enters_the_queue_with_reason_and_severity() -> None:
    report = analyze_invalid_boxes(_dataset_with_invalid_box(), _config())
    queue = build_reannotation_queue(report)

    assert len(queue) == 1
    item = queue[0]
    assert item.annotation_id == 1
    assert item.image_id == IMAGE_ID
    assert "negative_coordinates" in item.reason
    assert item.analyzer == "invalid_boxes"
    assert item.severity == "fail"


def test_valid_boxes_never_enter_the_queue() -> None:
    report = analyze_invalid_boxes(_dataset_with_corrected_box(), _config())
    queue = build_reannotation_queue(report)

    assert queue == []


def test_correcting_a_sample_removes_it_from_the_queue() -> None:
    # CAL 10, criterio de cierre: "una muestra corregida puede salir de la
    # cola después de volver a ejecutar la validación".
    report_before = analyze_invalid_boxes(_dataset_with_invalid_box(), _config())
    queue_before = build_reannotation_queue(report_before)
    assert len(queue_before) == 1

    report_after = analyze_invalid_boxes(_dataset_with_corrected_box(), _config())
    queue_after = build_reannotation_queue(report_after)
    assert queue_after == []
