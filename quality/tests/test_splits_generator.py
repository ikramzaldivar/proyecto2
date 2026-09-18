from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import SplitConfig
from dataset_quality.splits.generator import generate_splits

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


def _build_dataset(num_car: int = 6, num_person: int = 6) -> CocoDataset:
    # Imágenes 1..num_car son solo "car"; las siguientes num_person son
    # solo "person" — sin traslape, para que sea fácil razonar el resultado.
    total = num_car + num_person
    images = [_image(i) for i in range(1, total + 1)]
    annotations = [_annotation(i, i, CAR_ID) for i in range(1, num_car + 1)]
    annotations += [
        _annotation(i, i, PERSON_ID) for i in range(num_car + 1, num_car + num_person + 1)
    ]
    return CocoDataset.model_validate(
        {
            "images": images,
            "categories": [{"id": CAR_ID, "name": "car"}, {"id": PERSON_ID, "name": "person"}],
            "annotations": annotations,
        }
    )


def _default_config() -> SplitConfig:
    return SplitConfig(train=0.7, val=0.15, test=0.15, seed=42)


def test_splits_sum_to_the_total_number_of_images() -> None:
    dataset = _build_dataset()
    result = generate_splits(dataset, duplicate_groups=[], config=_default_config())

    total_assigned = len(result.train) + len(result.val) + len(result.test)
    assert total_assigned == len(dataset.images)


def test_no_leakage_between_splits() -> None:
    dataset = _build_dataset()
    result = generate_splits(dataset, duplicate_groups=[], config=_default_config())

    assert set(result.train) & set(result.val) == set()
    assert set(result.train) & set(result.test) == set()
    assert set(result.val) & set(result.test) == set()


def test_val_and_test_contain_all_categories() -> None:
    # CAL 09, criterio de cierre: "val y test contienen todas las clases".
    dataset = _build_dataset()
    result = generate_splits(dataset, duplicate_groups=[], config=_default_config())

    car_images = set(range(1, 7))
    person_images = set(range(7, 13))

    assert set(result.val) & car_images
    assert set(result.val) & person_images
    assert set(result.test) & car_images
    assert set(result.test) & person_images


def test_same_seed_produces_identical_splits() -> None:
    # CAL 09, criterio de cierre: "correr dos veces con la misma seed" ->
    # mismo resultado exacto.
    dataset = _build_dataset()
    config = _default_config()

    result_a = generate_splits(dataset, duplicate_groups=[], config=config)
    result_b = generate_splits(dataset, duplicate_groups=[], config=config)

    assert result_a.train == result_b.train
    assert result_a.val == result_b.val
    assert result_a.test == result_b.test


def test_duplicate_cluster_always_stays_in_the_same_split() -> None:
    # CAL 09, criterio de cierre: "mantener imágenes duplicadas o cercanas
    # dentro de la misma partición" — imagen 1 y 2 son "el mismo" cluster
    # de duplicados, no deben quedar separadas nunca.
    dataset = _build_dataset()
    result = generate_splits(dataset, duplicate_groups=[[1, 2]], config=_default_config())

    split_of_1 = "train" if 1 in result.train else "val" if 1 in result.val else "test"
    split_of_2 = "train" if 2 in result.train else "val" if 2 in result.val else "test"
    assert split_of_1 == split_of_2
