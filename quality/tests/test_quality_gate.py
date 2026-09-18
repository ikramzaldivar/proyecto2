from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import QualityConfig
from dataset_quality.policy.quality_gate import evaluate_quality_gate

CAR_ID = 1
PERSON_ID = 2
IMAGE_WIDTH = 100
IMAGE_HEIGHT = 100


def _annotation(annotation_id: int, image_id: int, category_id: int, bbox: list[float]) -> dict:
    width, height = bbox[2], bbox[3]
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": bbox,
        "area": width * height,
        "iscrowd": 0,
    }


def _image(image_id: int) -> dict:
    return {
        "id": image_id,
        "file_name": f"img{image_id}.jpg",
        "width": IMAGE_WIDTH,
        "height": IMAGE_HEIGHT,
    }


def _clean_dataset() -> CocoDataset:
    # 2 imágenes de car, 2 de person — todas las cajas válidas.
    return CocoDataset.model_validate(
        {
            "images": [_image(1), _image(2), _image(3), _image(4)],
            "categories": [{"id": CAR_ID, "name": "car"}, {"id": PERSON_ID, "name": "person"}],
            "annotations": [
                _annotation(1, 1, CAR_ID, [10, 10, 20, 20]),
                _annotation(2, 2, CAR_ID, [10, 10, 20, 20]),
                _annotation(3, 3, PERSON_ID, [10, 10, 20, 20]),
                _annotation(4, 4, PERSON_ID, [10, 10, 20, 20]),
            ],
        }
    )


def _dataset_with_invalid_box() -> CocoDataset:
    dataset_dict = _clean_dataset().model_dump()
    dataset_dict["annotations"].append(
        _annotation(5, 1, CAR_ID, [-5, 10, 20, 20])  # coordenada negativa
    )
    return CocoDataset.model_validate(dataset_dict)


def _base_config(min_images_threshold: float, class_imbalance_severity: str = "warn") -> dict:
    return {
        "checks": {
            "min_images_per_class": {
                "threshold": min_images_threshold,
                "min_classes": 2,
                "severity": "fail",
            },
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {"threshold": 10, "severity": class_imbalance_severity},
            "duplicates": {"threshold": 8, "severity": "warn"},
            "invalid_boxes": {"threshold": 0, "severity": "fail"},
            "spatial_bias": {"threshold": 0.5, "severity": "warn"},
        },
        "splits": {"train": 0.7, "val": 0.15, "test": 0.15, "seed": 42},
    }


def _run_gate(dataset: CocoDataset, config: QualityConfig):
    small_objects = analyze_small_objects(dataset, config.checks["small_objects"])
    class_imbalance = analyze_class_imbalance(
        dataset,
        config.checks["class_imbalance"],
        min_images_threshold=config.checks["min_images_per_class"].threshold,
    )
    duplicates = analyze_duplicates({}, config.checks["duplicates"])
    invalid_boxes = analyze_invalid_boxes(dataset, config.checks["invalid_boxes"])
    spatial_bias = analyze_spatial_bias(dataset, config.checks["spatial_bias"])

    return evaluate_quality_gate(
        config, small_objects, class_imbalance, duplicates, invalid_boxes, spatial_bias
    )


def test_gate_passes_with_clean_data_and_achievable_threshold() -> None:
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_clean_dataset(), config)

    assert result.overall_status == "pass"
    assert result.exit_code == 0


def test_impossible_min_images_threshold_fails_the_gate() -> None:
    # CAL 08, criterio de cierre: "un mínimo imposible hace fallar el comando".
    config = QualityConfig.model_validate(_base_config(min_images_threshold=1000))
    result = _run_gate(_clean_dataset(), config)

    assert result.overall_status == "fail"
    assert result.exit_code != 0

    min_images_check = next(c for c in result.checks if c.name == "min_images_per_class")
    assert min_images_check.status == "fail"


def test_restoring_the_threshold_produces_pass() -> None:
    # CAL 08, criterio de cierre: "restaurar el umbral produce PASS".
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_clean_dataset(), config)

    assert result.overall_status == "pass"
    assert result.exit_code == 0


def test_invalid_boxes_fail_the_gate() -> None:
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_dataset_with_invalid_box(), config)

    assert result.overall_status == "fail"
    invalid_check = next(c for c in result.checks if c.name == "invalid_boxes")
    assert invalid_check.status == "fail"
    assert len(invalid_check.samples) == 1


def test_warn_severity_does_not_block_overall_pass() -> None:
    config = QualityConfig.model_validate(
        _base_config(min_images_threshold=2, class_imbalance_severity="warn")
    )
    result = _run_gate(_clean_dataset(), config)

    class_imbalance_check = next(c for c in result.checks if c.name == "class_imbalance")
    assert class_imbalance_check.severity == "warn"
    assert result.overall_status == "pass"
