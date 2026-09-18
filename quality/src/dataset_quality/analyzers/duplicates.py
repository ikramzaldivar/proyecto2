from pydantic import BaseModel

from dataset_quality.models.config import CheckConfig, Severity


class DuplicatePair(BaseModel):
    image_id_a: int
    image_id_b: int
    distance: int


class DuplicatesReport(BaseModel):
    threshold: float
    severity: Severity
    pairs: list[DuplicatePair]
    duplicate_groups: list[list[int]]


def _hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compara dos hashes hexadecimales bit a bit (cuántos bits difieren)."""
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")


def _group_pairs(image_ids: list[int], pairs: list[DuplicatePair]) -> list[list[int]]:
    """Une pares en grupos transitivos (union-find): si A~B y B~C, los tres
    quedan en el mismo grupo aunque A y C nunca se hayan comparado
    directamente dentro del umbral."""
    parent = {image_id: image_id for image_id in image_ids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for pair in pairs:
        union(pair.image_id_a, pair.image_id_b)

    groups_by_root: dict[int, list[int]] = {}
    for image_id in image_ids:
        groups_by_root.setdefault(find(image_id), []).append(image_id)

    return [group for group in groups_by_root.values() if len(group) > 1]


def analyze_duplicates(image_hashes: dict[int, str], config: CheckConfig) -> DuplicatesReport:
    """Función pura (CAL 00): recibe los hashes YA calculados
    (image_id -> hash hex), no toca disco. Compara todos los pares y agrupa
    los que caen dentro del umbral de distancia configurado."""
    image_ids = list(image_hashes.keys())
    pairs: list[DuplicatePair] = []

    for i in range(len(image_ids)):
        for j in range(i + 1, len(image_ids)):
            id_a, id_b = image_ids[i], image_ids[j]
            distance = _hamming_distance(image_hashes[id_a], image_hashes[id_b])
            if distance <= config.threshold:
                pairs.append(DuplicatePair(image_id_a=id_a, image_id_b=id_b, distance=distance))

    return DuplicatesReport(
        threshold=config.threshold,
        severity=config.severity,
        pairs=pairs,
        duplicate_groups=_group_pairs(image_ids, pairs),
    )
