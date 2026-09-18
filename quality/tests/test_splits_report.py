"""Tests de CAL 09/10: distribución por split y verificación de fuga.

Datasets chiquitos armados a mano, con el resultado esperado calculado a
mano también: si el test y la implementación se equivocaran igual, el test
no serviría de nada.
"""

from dataset_quality.models.coco import CocoAnnotation, CocoCategory, CocoDataset, CocoImage
from dataset_quality.splits.generator import SplitAssignment
from dataset_quality.splits.report import build_leakage_report, build_split_distribution

PERSON = 1
CAR = 2


def _dataset(annotations: list[tuple[int, int]], image_ids: list[int] | None = None) -> CocoDataset:
    """annotations es una lista de (image_id, category_id). El bbox y el área
    dan igual aquí: estas dos funciones solo miran ids."""
    ids = image_ids if image_ids is not None else sorted({image_id for image_id, _ in annotations})
    return CocoDataset(
        images=[
            CocoImage(id=image_id, file_name=f"{image_id}.jpg", width=100, height=100)
            for image_id in ids
        ],
        annotations=[
            CocoAnnotation(
                id=index + 1,
                image_id=image_id,
                category_id=category_id,
                bbox=[0.0, 0.0, 10.0, 10.0],
                area=100.0,
                iscrowd=0,
            )
            for index, (image_id, category_id) in enumerate(annotations)
        ],
        categories=[
            CocoCategory(id=PERSON, name="person"),
            CocoCategory(id=CAR, name="car"),
        ],
    )


def test_distribution_counts_distinct_images_per_category():
    # Imagen 1 tiene DOS cajas de person: debe contar como una sola imagen.
    dataset = _dataset([(1, PERSON), (1, PERSON), (2, PERSON), (3, CAR), (4, CAR)])
    assignment = SplitAssignment(train=[1, 3], val=[2], test=[4])

    distribution = build_split_distribution(dataset, assignment)

    by_split = {entry.split: entry for entry in distribution}
    assert [entry.split for entry in distribution] == ["train", "val", "test"]

    assert by_split["train"].total_images == 2
    assert by_split["train"].category_counts == {"1": 1, "2": 1}

    assert by_split["val"].total_images == 1
    assert by_split["val"].category_counts == {"1": 1, "2": 0}

    assert by_split["test"].total_images == 1
    assert by_split["test"].category_counts == {"1": 0, "2": 1}


def test_distribution_keeps_categories_with_zero_images():
    # Una categoría sin ninguna imagen en el dataset sigue apareciendo en
    # todos los splits con 0: el portal necesita la fila para graficarla.
    dataset = _dataset([(1, PERSON), (2, PERSON)])
    assignment = SplitAssignment(train=[1], val=[2], test=[])

    distribution = build_split_distribution(dataset, assignment)

    assert {entry.split: entry.category_counts["2"] for entry in distribution} == {
        "train": 0,
        "val": 0,
        "test": 0,
    }
    assert [entry.total_images for entry in distribution] == [1, 1, 0]


def test_leakage_detects_duplicate_group_split_across_two_splits():
    # 1 y 2 son near-duplicates pero cayeron en splits distintos: fuga.
    dataset = _dataset([(1, PERSON), (2, PERSON), (3, CAR), (4, CAR)])
    assignment = SplitAssignment(train=[1, 3], val=[2], test=[4])
    distribution = build_split_distribution(dataset, assignment)

    leakage = build_leakage_report(dataset, assignment, [[1, 2]], distribution)

    assert leakage.id_intersection_size == 0
    assert leakage.leaked_image_ids == []
    assert leakage.cross_split_duplicate_pairs == 1
    assert leakage.duplicate_groups_within_one_split == 0
    assert leakage.all_classes_in_val is False
    assert leakage.all_classes_in_test is False


def test_leakage_clean_when_duplicate_group_stays_together():
    dataset = _dataset([(1, PERSON), (2, PERSON), (3, CAR), (4, CAR)])
    assignment = SplitAssignment(train=[1, 2], val=[3], test=[4])
    distribution = build_split_distribution(dataset, assignment)

    leakage = build_leakage_report(dataset, assignment, [[1, 2]], distribution)

    assert leakage.id_intersection_size == 0
    assert leakage.cross_split_duplicate_pairs == 0
    assert leakage.duplicate_groups_within_one_split == 1


def test_leakage_counts_every_cross_split_pair_of_a_group_of_three():
    # Grupo {1,2,3}: tres pares posibles. 1 en train, 2 y 3 en val ->
    # (1,2) y (1,3) cruzan; (2,3) no. Esperado: 2.
    dataset = _dataset([(1, PERSON), (2, PERSON), (3, PERSON), (4, CAR)])
    assignment = SplitAssignment(train=[1, 4], val=[2, 3], test=[])
    distribution = build_split_distribution(dataset, assignment)

    leakage = build_leakage_report(dataset, assignment, [[1, 2, 3]], distribution)

    assert leakage.cross_split_duplicate_pairs == 2
    assert leakage.duplicate_groups_within_one_split == 0


def test_leakage_reports_ids_present_in_more_than_one_split():
    dataset = _dataset([(1, PERSON), (2, PERSON), (3, CAR), (4, CAR)])
    # La imagen 2 aparece en train y en val a la vez.
    assignment = SplitAssignment(train=[1, 2], val=[2, 3], test=[4])
    distribution = build_split_distribution(dataset, assignment)

    leakage = build_leakage_report(dataset, assignment, [], distribution)

    assert leakage.id_intersection_size == 1
    assert leakage.leaked_image_ids == [2]


def test_leakage_confirms_full_class_coverage_in_val_and_test():
    dataset = _dataset(
        [(1, PERSON), (2, CAR), (3, PERSON), (4, CAR), (5, PERSON), (6, CAR)],
    )
    assignment = SplitAssignment(train=[1, 2], val=[3, 4], test=[5, 6])
    distribution = build_split_distribution(dataset, assignment)

    leakage = build_leakage_report(dataset, assignment, [], distribution)

    assert leakage.all_classes_in_val is True
    assert leakage.all_classes_in_test is True
