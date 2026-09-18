import random

from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import SplitConfig


class SplitAssignment(BaseModel):
    train: list[int]
    val: list[int]
    test: list[int]


def _build_clusters(image_ids: list[int], duplicate_groups: list[list[int]]) -> list[list[int]]:
    """Agrupa imágenes en clusters: cada grupo de duplicados/near-duplicates
    (de CAL 05) forma un cluster que se mueve junto a un único split —
    así se garantiza cero fuga por duplicados. Las imágenes sin duplicados
    quedan como clusters de una sola imagen."""
    grouped_ids: set[int] = set()
    clusters: list[list[int]] = []

    for group in duplicate_groups:
        cluster = sorted(set(group) & set(image_ids))
        if cluster:
            clusters.append(cluster)
            grouped_ids.update(cluster)

    for image_id in image_ids:
        if image_id not in grouped_ids:
            clusters.append([image_id])

    # Orden determinístico ANTES de barajar (pedido explícito de CAL 09:
    # "ordenar entradas antes de sortear") — sin esto, el orden de entrada
    # del dataset podría afectar el resultado incluso con la misma seed.
    clusters.sort(key=lambda cluster: cluster[0])
    return clusters


def _categories_by_image(dataset: CocoDataset) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {}
    for annotation in dataset.annotations:
        result.setdefault(annotation.image_id, set()).add(annotation.category_id)
    return result


def generate_splits(
    dataset: CocoDataset, duplicate_groups: list[list[int]], config: SplitConfig
) -> SplitAssignment:
    """Función pura (CAL 00). Genera train/val/test reproducibles:

    - Los clusters de duplicados/near-duplicates SIEMPRE quedan juntos en
      el mismo split (cero fuga).
    - El orden se fija antes de barajar; el barajado usa random.Random(seed)
      -> misma seed, mismo resultado siempre, en cualquier corrida.
    - Antes del reparto proporcional, se garantiza EXPLÍCITAMENTE que val y
      test tengan al menos un cluster de cada categoría — no se deja al
      azar del barajado, que podría fallar en datasets chicos.
    - El resto se reparte proporcionalmente (greedy: cada cluster va al
      split que más lejos esté, en conteo de imágenes, de su proporción
      configurada).
    """
    image_ids = [image.id for image in dataset.images]
    clusters = _build_clusters(image_ids, duplicate_groups)
    categories_by_image = _categories_by_image(dataset)

    def cluster_categories(cluster: list[int]) -> set[int]:
        result: set[int] = set()
        for image_id in cluster:
            result |= categories_by_image.get(image_id, set())
        return result

    all_category_ids = sorted(category.id for category in dataset.categories)

    rng = random.Random(config.seed)
    shuffled_clusters = clusters.copy()
    rng.shuffle(shuffled_clusters)

    assigned: dict[str, list[list[int]]] = {"train": [], "val": [], "test": []}
    used_indices: set[int] = set()

    # Paso 1: garantizar cobertura de TODAS las categorías en val y test.
    for split_name in ("val", "test"):
        for category_id in all_category_ids:
            already_covered = any(
                category_id in cluster_categories(cluster) for cluster in assigned[split_name]
            )
            if already_covered:
                continue

            candidate_index = next(
                (
                    index
                    for index, cluster in enumerate(shuffled_clusters)
                    if index not in used_indices and category_id in cluster_categories(cluster)
                ),
                None,
            )
            if candidate_index is not None:
                assigned[split_name].append(shuffled_clusters[candidate_index])
                used_indices.add(candidate_index)

    # Paso 2: reparto proporcional del resto de los clusters.
    total = len(image_ids)
    targets = {"train": config.train, "val": config.val, "test": config.test}
    counts = {
        name: sum(len(cluster) for cluster in clusters_list)
        for name, clusters_list in assigned.items()
    }

    for index, cluster in enumerate(shuffled_clusters):
        if index in used_indices:
            continue

        def deficit(split_name: str) -> float:
            return targets[split_name] * total - counts[split_name]

        chosen = max(targets, key=deficit)
        assigned[chosen].append(cluster)
        counts[chosen] += len(cluster)

    return SplitAssignment(
        train=sorted(image_id for cluster in assigned["train"] for image_id in cluster),
        val=sorted(image_id for cluster in assigned["val"] for image_id in cluster),
        test=sorted(image_id for cluster in assigned["test"] for image_id in cluster),
    )
