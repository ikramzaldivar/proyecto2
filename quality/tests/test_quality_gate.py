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

ALL_CHECK_NAMES = {
    "min_images_per_class",
    "small_objects",
    "class_imbalance",
    "duplicates",
    "invalid_boxes",
    "spatial_bias",
}


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
    # 2 imágenes de car, 2 de person — todas las cajas válidas, ratio 1:1.
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


def _imbalanced_dataset() -> CocoDataset:
    # 3 imágenes de car, 1 de person -> ratio 3.0.
    return CocoDataset.model_validate(
        {
            "images": [_image(1), _image(2), _image(3), _image(4)],
            "categories": [{"id": CAR_ID, "name": "car"}, {"id": PERSON_ID, "name": "person"}],
            "annotations": [
                _annotation(1, 1, CAR_ID, [10, 10, 20, 20]),
                _annotation(2, 2, CAR_ID, [10, 10, 20, 20]),
                _annotation(3, 3, CAR_ID, [10, 10, 20, 20]),
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


def _base_config(
    min_images_threshold: float,
    class_imbalance_threshold: float = 10,
    class_imbalance_severity: str = "warn",
) -> dict:
    return {
        "checks": {
            "min_images_per_class": {
                "threshold": min_images_threshold,
                "min_classes": 2,
                "severity": "fail",
            },
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {
                "threshold": class_imbalance_threshold,
                "severity": class_imbalance_severity,
            },
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


def test_config_satisfying_everything_allows_the_release() -> None:
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


def test_a_fail_severity_check_really_blocks_the_release() -> None:
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_dataset_with_invalid_box(), config)

    invalid_check = next(c for c in result.checks if c.name == "invalid_boxes")
    assert invalid_check.status == "fail"
    assert invalid_check.observed["invalid_count"] == 1
    assert len(invalid_check.samples) == 1
    assert result.overall_status == "fail"
    assert result.exit_code != 0


def test_a_warn_severity_check_does_not_block_the_release() -> None:
    # class_imbalance con severidad warn, con un dataset genuinamente
    # desbalanceado (ratio 3.0) y un threshold bajo (1) para que SÍ se
    # dispare de verdad — no solo que se quede en "pass" por no aplicar.
    config = QualityConfig.model_validate(
        _base_config(
            min_images_threshold=1, class_imbalance_threshold=1, class_imbalance_severity="warn"
        )
    )
    result = _run_gate(_imbalanced_dataset(), config)

    class_imbalance_check = next(c for c in result.checks if c.name == "class_imbalance")
    assert class_imbalance_check.status == "warn"
    assert class_imbalance_check.observed["ratio"] == 3.0

    # El warn debe aparecer en el reporte, pero NO bloquear el release.
    assert result.overall_status == "pass"
    assert result.exit_code == 0


def test_report_keeps_results_of_all_six_checks() -> None:
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_clean_dataset(), config)

    assert {check.name for check in result.checks} == ALL_CHECK_NAMES
    assert len(result.checks) == 6


def test_small_objects_and_spatial_bias_report_full_stats_without_blocking() -> None:
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_clean_dataset(), config)

    small_objects_check = next(c for c in result.checks if c.name == "small_objects")
    assert small_objects_check.status == "pass"
    assert "small_percent" in small_objects_check.observed
    assert "percent_by_category" in small_objects_check.observed

    spatial_bias_check = next(c for c in result.checks if c.name == "spatial_bias")
    assert spatial_bias_check.status == "pass"
    assert "global_stats" in spatial_bias_check.observed
    assert "stats_by_category" in spatial_bias_check.observed


def test_small_objects_produces_warn_when_max_percent_is_configured_and_exceeded() -> None:
    # C-13: max_small_percent es opcional; si está configurado y se supera,
    # el check debe dispararse -- ya no queda fijo en "pass".
    config_dict = _base_config(min_images_threshold=2)
    config_dict["checks"]["small_objects"]["max_small_percent"] = 10
    config = QualityConfig.model_validate(config_dict)

    result = _run_gate(_clean_dataset(), config)  # todas las cajas son 20x20, < 32px

    small_objects_check = next(c for c in result.checks if c.name == "small_objects")
    assert small_objects_check.status == "warn"
    assert result.overall_status == "pass"
    assert result.exit_code == 0


def test_small_objects_blocks_the_release_when_severity_is_fail() -> None:
    config_dict = _base_config(min_images_threshold=2)
    config_dict["checks"]["small_objects"]["max_small_percent"] = 10
    config_dict["checks"]["small_objects"]["severity"] = "fail"
    config = QualityConfig.model_validate(config_dict)

    result = _run_gate(_clean_dataset(), config)

    small_objects_check = next(c for c in result.checks if c.name == "small_objects")
    assert small_objects_check.status == "fail"
    assert result.overall_status == "fail"
    assert result.exit_code != 0


def test_small_objects_stays_informational_without_a_configured_max_percent() -> None:
    # Sin max_small_percent en el YAML (caso de hoy en quality.yaml real),
    # el check sigue siendo puramente informativo -- no rompe nada existente.
    config = QualityConfig.model_validate(_base_config(min_images_threshold=2))
    result = _run_gate(_clean_dataset(), config)  # mismas cajas pequeñas de arriba

    small_objects_check = next(c for c in result.checks if c.name == "small_objects")
    assert small_objects_check.status == "pass"
