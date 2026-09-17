from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.models.coco import CocoAnnotation, CocoCategory, CocoDataset, CocoImage
from dataset_quality.models.config import CheckConfig

# Umbral: 32 px -> área mínima = 32*32 = 1024 px².
#
# Anotaciones (bbox = [x, y, width, height], área = width * height):
#   1) car,    10x10 = 100   -> PEQUEÑA
#   2) car,    50x50 = 2500  -> normal
#   3) person, 5x5   = 25    -> PEQUEÑA
#   4) person, 100x100 = 10000 -> normal
#   5) person, 3x3   = 9     -> PEQUEÑA
#
# Cálculo a mano:
#   total = 5, pequeñas = 3 (1, 3, 5) -> 60.0%
#   car:    total 2, pequeñas 1 -> 50.0%
#   person: total 3, pequeñas 2 -> 66.666...%
#   clase más afectada: person (66.67% > 50%)

CAR_ID = 1
PERSON_ID = 2


def _build_dataset() -> CocoDataset:
    return CocoDataset.model_validate(
        {
            "images": [{"id": 1, "file_name": "a.jpg", "width": 1000, "height": 1000}],
            "categories": [
                {"id": CAR_ID, "name": "car"},
                {"id": PERSON_ID, "name": "person"},
            ],
            "annotations": [
                {"id": 1, "image_id": 1, "category_id": CAR_ID, "bbox": [0, 0, 10, 10], "area": 100, "iscrowd": 0},
                {"id": 2, "image_id": 1, "category_id": CAR_ID, "bbox": [0, 0, 50, 50], "area": 2500, "iscrowd": 0},
                {"id": 3, "image_id": 1, "category_id": PERSON_ID, "bbox": [0, 0, 5, 5], "area": 25, "iscrowd": 0},
                {"id": 4, "image_id": 1, "category_id": PERSON_ID, "bbox": [0, 0, 100, 100], "area": 10000, "iscrowd": 0},
                {"id": 5, "image_id": 1, "category_id": PERSON_ID, "bbox": [0, 0, 3, 3], "area": 9, "iscrowd": 0},
            ],
        }
    )


def test_reports_total_and_percent_of_small_objects() -> None:
    report = analyze_small_objects(_build_dataset(), CheckConfig(threshold=32, severity="warn"))

    assert report.total_annotations == 5
    assert report.small_count == 3
    assert report.small_percent == 60.0


def test_reports_percent_by_category() -> None:
    report = analyze_small_objects(_build_dataset(), CheckConfig(threshold=32, severity="warn"))

    assert report.percent_by_category[CAR_ID] == 50.0
    assert round(report.percent_by_category[PERSON_ID], 2) == 66.67


def test_identifies_most_affected_category() -> None:
    report = analyze_small_objects(_build_dataset(), CheckConfig(threshold=32, severity="warn"))

    assert report.most_affected_category_id == PERSON_ID


def test_lists_offending_samples_with_their_dimensions() -> None:
    report = analyze_small_objects(_build_dataset(), CheckConfig(threshold=32, severity="warn"))

    offending_ids = {sample.annotation_id for sample in report.offending_samples}
    assert offending_ids == {1, 3, 5}


def test_changing_the_threshold_changes_the_result() -> None:
    # CAL 03: "cambiar el YAML cambia el resultado" — aquí simulamos ese
    # cambio pasando un CheckConfig distinto, sin tocar el analizador.
    lenient_report = analyze_small_objects(_build_dataset(), CheckConfig(threshold=4, severity="warn"))

    # Con umbral 4px (área mínima 16), solo la anotación 5 (3x3=9) califica.
    assert lenient_report.small_count == 1
    assert lenient_report.offending_samples[0].annotation_id == 5


def test_empty_dataset_does_not_divide_by_zero() -> None:
    empty_dataset = CocoDataset.model_validate({"images": [], "annotations": [], "categories": []})
    report = analyze_small_objects(empty_dataset, CheckConfig(threshold=32, severity="warn"))

    assert report.total_annotations == 0
    assert report.small_percent == 0.0
    assert report.most_affected_category_id is None
