import pytest
from pydantic import ValidationError

from dataset_quality.models.coco import CocoDataset


def _valid_dataset_kwargs() -> dict:
    return {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            }
        ],
        "categories": [{"id": 1, "name": "car"}],
    }


def test_valid_dataset_is_accepted() -> None:
    dataset = CocoDataset.model_validate(_valid_dataset_kwargs())
    assert dataset.images[0].id == 1
    assert dataset.annotations[0].bbox == [10, 10, 20, 20]


def test_rejects_bbox_with_wrong_length() -> None:
    # CAL 01: "un bbox corto" — el COCO exige exactamente [x, y, width, height].
    payload = _valid_dataset_kwargs()
    payload["annotations"][0]["bbox"] = [10, 10, 20]

    with pytest.raises(ValidationError, match="bbox"):
        CocoDataset.model_validate(payload)


def test_rejects_annotation_with_nonexistent_category() -> None:
    # CAL 01: "una categoría inexistente".
    payload = _valid_dataset_kwargs()
    payload["annotations"][0]["category_id"] = 999

    with pytest.raises(ValidationError, match="category_id"):
        CocoDataset.model_validate(payload)


def test_rejects_annotation_with_orphan_image() -> None:
    # CAL 01: "una imagen huérfana" — la anotación apunta a un image_id que
    # no está en la sección "images".
    payload = _valid_dataset_kwargs()
    payload["annotations"][0]["image_id"] = 999

    with pytest.raises(ValidationError, match="image_id"):
        CocoDataset.model_validate(payload)
