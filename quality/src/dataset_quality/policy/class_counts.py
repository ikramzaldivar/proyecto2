from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset


class ClassCountComparison(BaseModel):
    category_id: int
    distinct_images_before: int
    distinct_images_after: int


def count_distinct_images_before_and_after_duplicates(
    dataset: CocoDataset, duplicate_groups: list[list[int]]
) -> list[ClassCountComparison]:
    """Función pura (CAL 00). "Antes": cuenta cada imagen individualmente,
    tal como está anotada. "Después": colapsa cada grupo de
    duplicados/near-duplicates (CAL 05) a UNA sola imagen representativa
    antes de contar — así una clase no queda inflada por copias.

    Esto responde directamente a M3 de la rúbrica de evaluación: "cuenta
    el conteo antes y después de colapsar duplicados; si al colapsar
    alguna clase baja de 300, el requisito no se cumple"."""
    images_by_category: dict[int, set[int]] = {}
    for annotation in dataset.annotations:
        images_by_category.setdefault(annotation.category_id, set()).add(annotation.image_id)

    # Cada imagen de un grupo de duplicados apunta a un mismo
    # "representante" (el id más chico del grupo) — así, al contar con un
    # set, todas las copias de ese grupo cuentan como una sola imagen.
    representative_of: dict[int, int] = {}
    for group in duplicate_groups:
        representative = min(group)
        for image_id in group:
            representative_of[image_id] = representative

    results: list[ClassCountComparison] = []
    for category in dataset.categories:
        images = images_by_category.get(category.id, set())
        after = {representative_of.get(image_id, image_id) for image_id in images}
        results.append(
            ClassCountComparison(
                category_id=category.id,
                distinct_images_before=len(images),
                distinct_images_after=len(after),
            )
        )
    return results
