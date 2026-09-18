"""Distribución por split y verificación de fuga (CAL 09/10).

Dos funciones puras (CAL 00) sobre el resultado de `generate_splits`: no
tocan disco, red ni entorno. Los nombres de campo de los modelos son los
que el portal ya espera — ver `splitDistributionSchema` y
`leakageReportSchema` en `backend/src/logic/quality/contracts.ts`.

`generate_splits` ya mantiene cada grupo de duplicados dentro de un solo
split. Estas funciones NO confían en eso: lo verifican y lo reportan en
números, que es justo el punto de una compuerta.
"""

from itertools import combinations
from typing import Literal

from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.splits.generator import SplitAssignment

SplitName = Literal["train", "val", "test"]

SPLIT_NAMES: tuple[SplitName, ...] = ("train", "val", "test")


class SplitDistribution(BaseModel):
    """Cuántas imágenes distintas hay por categoría dentro de un split.

    `category_counts` lleva llaves de tipo string porque así viaja en JSON
    y así lo valida el portal. Incluye SIEMPRE todas las categorías del
    dataset, con 0 cuando el split no tiene ninguna: una categoría que
    desaparece de la tabla es indistinguible de una que nadie graficó.
    """

    split: SplitName
    total_images: int
    category_counts: dict[str, int]


class LeakageReport(BaseModel):
    """Resultado de buscar fuga entre splits.

    - `id_intersection_size` / `leaked_image_ids`: la misma imagen metida
      en dos splits. Debe ser 0 y [].
    - `cross_split_duplicate_pairs`: pares de near-duplicates que quedaron
      repartidos en splits sin nada en común. Debe ser 0.
    - `duplicate_groups_within_one_split`: grupos que sí quedaron enteros
      en un solo split. Es el contador "bueno": debe igualar al total de
      grupos de duplicados del dataset.
    """

    id_intersection_size: int
    cross_split_duplicate_pairs: int
    duplicate_groups_within_one_split: int
    leaked_image_ids: list[int]
    all_classes_in_val: bool
    all_classes_in_test: bool


def _images_by_category(dataset: CocoDataset) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {}
    for annotation in dataset.annotations:
        result.setdefault(annotation.category_id, set()).add(annotation.image_id)
    return result


def _splits_of_each_image(assignment: SplitAssignment) -> dict[int, set[SplitName]]:
    """Mapa imagen -> splits que la contienen. Es un SET y no un solo valor
    a propósito: si una imagen aparece en dos splits, eso es exactamente la
    fuga que queremos detectar, no un caso imposible que podamos aplastar."""
    result: dict[int, set[SplitName]] = {}
    for split_name in SPLIT_NAMES:
        for image_id in getattr(assignment, split_name):
            result.setdefault(image_id, set()).add(split_name)
    return result


def build_split_distribution(
    dataset: CocoDataset, assignment: SplitAssignment
) -> list[SplitDistribution]:
    """Cuenta, por split y por categoría, cuántas IMÁGENES DISTINTAS hay.

    Cuenta imágenes, no cajas: una imagen con tres cajas de `person` suma
    uno, no tres. Es el mismo criterio que usa `analyze_class_imbalance`.
    """
    images_by_category = _images_by_category(dataset)
    category_ids = sorted(category.id for category in dataset.categories)

    distribution: list[SplitDistribution] = []
    for split_name in SPLIT_NAMES:
        split_image_ids = set(getattr(assignment, split_name))
        counts = {
            str(category_id): len(images_by_category.get(category_id, set()) & split_image_ids)
            for category_id in category_ids
        }
        distribution.append(
            SplitDistribution(
                split=split_name,
                total_images=len(split_image_ids),
                category_counts=counts,
            )
        )
    return distribution


def build_leakage_report(
    dataset: CocoDataset,
    assignment: SplitAssignment,
    duplicate_groups: list[list[int]],
    distribution: list[SplitDistribution],
) -> LeakageReport:
    """Verifica que ningún id esté en dos splits y que ningún grupo de
    near-duplicates haya quedado partido.

    Un par de duplicados cuenta como fuga cuando las imágenes no comparten
    NINGÚN split. Si una de las dos está en dos splits y una coincidencia
    existe, ese par no se reporta: la fuga real ahí es el id repetido, y
    ese ya sale por `leaked_image_ids`. Contarlo dos veces inflaría el
    reporte y escondería el problema de fondo.
    """
    splits_of = _splits_of_each_image(assignment)

    leaked_image_ids = sorted(
        image_id for image_id, split_names in splits_of.items() if len(split_names) > 1
    )

    cross_split_pairs = 0
    groups_within_one_split = 0
    for group in duplicate_groups:
        assigned = [image_id for image_id in group if splits_of.get(image_id)]
        if not assigned:
            continue

        for image_a, image_b in combinations(assigned, 2):
            if splits_of[image_a].isdisjoint(splits_of[image_b]):
                cross_split_pairs += 1

        shared: set[SplitName] = set(SPLIT_NAMES)
        for image_id in assigned:
            shared &= splits_of[image_id]
        if shared:
            groups_within_one_split += 1

    by_split = {entry.split: entry for entry in distribution}

    def covers_every_category(split_name: SplitName) -> bool:
        entry = by_split.get(split_name)
        if entry is None or not entry.category_counts:
            return False
        return all(count > 0 for count in entry.category_counts.values())

    return LeakageReport(
        id_intersection_size=len(leaked_image_ids),
        cross_split_duplicate_pairs=cross_split_pairs,
        duplicate_groups_within_one_split=groups_within_one_split,
        leaked_image_ids=leaked_image_ids,
        all_classes_in_val=covers_every_category("val"),
        all_classes_in_test=covers_every_category("test"),
    )
