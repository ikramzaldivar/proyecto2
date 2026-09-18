from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig

# Categorías: car, person, dog, bicycle (bicycle nunca se usa en ninguna
# anotación — caso de clase completamente vacía).
#
# car:    3 imágenes distintas (img1 con 2 cajas, img2, img3), 4 cajas
# person: 2 imágenes distintas, 2 cajas
# dog:    1 imagen distinta,    1 caja
# bicycle: 0 imágenes, 0 cajas
#
# Cálculo a mano:
#   ratio mayoría/minoría (por IMÁGENES DISTINTAS, no cajas) = car/dog = 3/1 = 3.0
#   con umbral de "mínimo de imágenes" = 2: por debajo quedan dog (1) y
#   bicycle (0) — person (2) NO queda por debajo (2 no es menor que 2).

CAR_ID = 1
PERSON_ID = 2
DOG_ID = 3
BICYCLE_ID = 4


def _annotation(annotation_id: int, image_id: int, category_id: int) -> dict:
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": [0, 0, 10, 10],
        "area": 100,
        "iscrowd": 0,
    }


def _image(image_id: int) -> dict:
    return {"id": image_id, "file_name": f"img{image_id}.jpg", "width": 100, "height": 100}


def _build_dataset() -> CocoDataset:
    return CocoDataset.model_validate(
        {
            "images": [_image(i) for i in range(1, 7)],
            "categories": [
                {"id": CAR_ID, "name": "car"},
                {"id": PERSON_ID, "name": "person"},
                {"id": DOG_ID, "name": "dog"},
                {"id": BICYCLE_ID, "name": "bicycle"},
            ],
            "annotations": [
                _annotation(1, 1, CAR_ID),
                _annotation(2, 1, CAR_ID),  # img1 tiene 2 cajas de car
                _annotation(3, 2, CAR_ID),
                _annotation(4, 3, CAR_ID),
                _annotation(5, 4, PERSON_ID),
                _annotation(6, 5, PERSON_ID),
                _annotation(7, 6, DOG_ID),
            ],
        }
    )


def test_counts_distinct_images_and_boxes_separately() -> None:
    report = analyze_class_imbalance(
        _build_dataset(), CheckConfig(threshold=10, severity="warn"), min_images_threshold=2
    )
    by_category = {d.category_id: d for d in report.distributions}

    # car: 3 imágenes distintas, pero 4 cajas (img1 tiene 2) — no deben confundirse.
    assert by_category[CAR_ID].distinct_image_count == 3
    assert by_category[CAR_ID].box_count == 4
    assert by_category[PERSON_ID].distinct_image_count == 2
    assert by_category[PERSON_ID].box_count == 2
    assert by_category[DOG_ID].distinct_image_count == 1
    assert by_category[BICYCLE_ID].distinct_image_count == 0


def test_computes_ratio_by_distinct_images_not_boxes() -> None:
    report = analyze_class_imbalance(
        _build_dataset(), CheckConfig(threshold=10, severity="warn"), min_images_threshold=2
    )

    assert report.majority_category_id == CAR_ID
    assert report.minority_category_id == DOG_ID
    assert report.ratio == 3.0


def test_lists_classes_below_min_images_threshold() -> None:
    report = analyze_class_imbalance(
        _build_dataset(), CheckConfig(threshold=10, severity="warn"), min_images_threshold=2
    )

    # dog (1) y bicycle (0) están por debajo de 2. person (2) NO lo está.
    assert set(report.classes_below_min_images) == {DOG_ID, BICYCLE_ID}
    assert PERSON_ID not in report.classes_below_min_images


def test_empty_category_does_not_break_ratio_calculation() -> None:
    # bicycle tiene 0 imágenes — no debe romper el cálculo del ratio (que
    # solo debe considerar categorías con al menos 1 imagen).
    report = analyze_class_imbalance(
        _build_dataset(), CheckConfig(threshold=10, severity="warn"), min_images_threshold=2
    )
    assert report.minority_category_id != BICYCLE_ID


def test_empty_dataset_reports_no_majority_or_minority() -> None:
    empty_dataset = CocoDataset.model_validate({"images": [], "annotations": [], "categories": []})
    report = analyze_class_imbalance(
        empty_dataset, CheckConfig(threshold=10, severity="warn"), min_images_threshold=300
    )

    assert report.majority_category_id is None
    assert report.minority_category_id is None
    assert report.ratio is None
    assert report.classes_below_min_images == []
