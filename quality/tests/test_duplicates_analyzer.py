from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.models.config import CheckConfig

# Hashes hexadecimales sintéticos (NO calculados de imágenes reales) — solo
# para probar la lógica de distancia/agrupamiento de forma controlada y
# rápida, sin depender de PIL/imagehash aquí. La prueba con imágenes reales
# vive en test_phash_adapter.py.


def test_pairs_images_within_the_distance_threshold() -> None:
    hashes = {
        1: "ffffffffffffffff",  # todo 1s
        2: "fffffffffffffffe",  # difiere de 1 en exactamente 1 bit
        3: "0000000000000000",  # todo 0s -> muy distinto de 1 y 2
    }
    report = analyze_duplicates(hashes, CheckConfig(threshold=2, severity="warn"))

    assert len(report.pairs) == 1
    assert report.pairs[0].image_id_a == 1
    assert report.pairs[0].image_id_b == 2
    assert report.pairs[0].distance == 1


def test_groups_transitively_duplicate_images_together() -> None:
    # 1~2 y 2~3 (pero 1 y 3 no se comparan directo) deben terminar en el
    # MISMO grupo, no en dos pares sueltos.
    hashes = {
        1: "ffffffffffffff00",
        2: "ffffffffffffff01",  # 1 bit distinto de 1
        3: "ffffffffffffff03",  # 1 bit distinto de 2, pero 2 bits distinto de 1
    }
    report = analyze_duplicates(hashes, CheckConfig(threshold=1, severity="warn"))

    assert report.duplicate_groups == [[1, 2, 3]]


def test_no_pairs_when_all_hashes_are_far_apart() -> None:
    hashes = {1: "ffffffffffffffff", 2: "0000000000000000", 3: "f0f0f0f0f0f0f0f0"}
    report = analyze_duplicates(hashes, CheckConfig(threshold=1, severity="warn"))

    assert report.pairs == []
    assert report.duplicate_groups == []


def test_single_image_produces_no_pairs() -> None:
    report = analyze_duplicates({1: "ffffffffffffffff"}, CheckConfig(threshold=8, severity="warn"))
    assert report.pairs == []
    assert report.duplicate_groups == []
