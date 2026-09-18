from dataset_quality.models.coco import CocoDataset
from dataset_quality.policy.class_counts import count_distinct_images_before_and_after_duplicates

CAR_ID = 1
PERSON_ID = 2


def _image(image_id: int) -> dict:
    return {"id": image_id, "file_name": f"img{image_id}.jpg", "width": 100, "height": 100}


def _annotation(annotation_id: int, image_id: int, category_id: int) -> dict:
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": [10, 10, 20, 20],
        "area": 400,
        "iscrowd": 0,
    }


def _build_dataset() -> CocoDataset:
    # car aparece en las imágenes 1,2,3,4,5 (5 distintas ANTES).
    # Las imágenes 1 y 2 son duplicados entre sí -> 4 distintas DESPUÉS.
    # person aparece en 6,7,8 (3 distintas, sin duplicados -> sigue en 3).
    return CocoDataset.model_validate(
        {
            "images": [_image(i) for i in range(1, 9)],
            "categories": [{"id": CAR_ID, "name": "car"}, {"id": PERSON_ID, "name": "person"}],
            "annotations": [
                _annotation(1, 1, CAR_ID),
                _annotation(2, 2, CAR_ID),
                _annotation(3, 3, CAR_ID),
                _annotation(4, 4, CAR_ID),
                _annotation(5, 5, CAR_ID),
                _annotation(6, 6, PERSON_ID),
                _annotation(7, 7, PERSON_ID),
                _annotation(8, 8, PERSON_ID),
            ],
        }
    )


def test_counts_are_the_same_before_and_after_when_there_are_no_duplicates() -> None:
    dataset = _build_dataset()
    results = count_distinct_images_before_and_after_duplicates(dataset, duplicate_groups=[])
    by_category = {r.category_id: r for r in results}

    assert by_category[CAR_ID].distinct_images_before == 5
    assert by_category[CAR_ID].distinct_images_after == 5
    assert by_category[PERSON_ID].distinct_images_before == 3
    assert by_category[PERSON_ID].distinct_images_after == 3


def test_collapsing_a_duplicate_pair_reduces_the_after_count() -> None:
    # Imágenes 1 y 2 (ambas "car") son duplicados -> deben colapsar a 1
    # sola imagen representativa al contar "después".
    dataset = _build_dataset()
    results = count_distinct_images_before_and_after_duplicates(dataset, duplicate_groups=[[1, 2]])
    by_category = {r.category_id: r for r in results}

    assert by_category[CAR_ID].distinct_images_before == 5
    assert by_category[CAR_ID].distinct_images_after == 4  # 5 - 1 por el colapso
    # person no tiene duplicados, no debe verse afectado.
    assert by_category[PERSON_ID].distinct_images_before == 3
    assert by_category[PERSON_ID].distinct_images_after == 3
