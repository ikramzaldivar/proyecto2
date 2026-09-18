import math
import statistics

from pydantic import BaseModel

from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig, Severity


class SpatialStats(BaseModel):
    count: int
    mean_x: float
    mean_y: float
    median_x: float
    median_y: float
    std_x: float
    std_y: float
    p25_x: float
    p75_x: float
    p25_y: float
    p75_y: float


class SpatialBiasReport(BaseModel):
    threshold: float
    severity: Severity
    global_stats: SpatialStats
    stats_by_category: dict[int, SpatialStats]


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Percentil por 'rango más cercano' (nearest-rank): simple y
    determinístico, sin interpolación — fácil de verificar a mano."""
    if not sorted_values:
        return 0.0
    index = max(0, math.ceil(percentile / 100 * len(sorted_values)) - 1)
    return sorted_values[min(index, len(sorted_values) - 1)]


def _empty_stats() -> SpatialStats:
    return SpatialStats(
        count=0,
        mean_x=0.0,
        mean_y=0.0,
        median_x=0.0,
        median_y=0.0,
        std_x=0.0,
        std_y=0.0,
        p25_x=0.0,
        p75_x=0.0,
        p25_y=0.0,
        p75_y=0.0,
    )


def _compute_stats(centers: list[tuple[float, float]]) -> SpatialStats:
    if not centers:
        return _empty_stats()

    xs = sorted(center[0] for center in centers)
    ys = sorted(center[1] for center in centers)

    return SpatialStats(
        count=len(centers),
        mean_x=statistics.mean(xs),
        mean_y=statistics.mean(ys),
        median_x=statistics.median(xs),
        median_y=statistics.median(ys),
        std_x=statistics.pstdev(xs),
        std_y=statistics.pstdev(ys),
        p25_x=_percentile(xs, 25),
        p75_x=_percentile(xs, 75),
        p25_y=_percentile(ys, 25),
        p75_y=_percentile(ys, 75),
    )


def analyze_spatial_bias(dataset: CocoDataset, config: CheckConfig) -> SpatialBiasReport:
    """Función pura (CAL 00). Normaliza el centro de cada caja respecto al
    tamaño de SU imagen (0-1 en ambos ejes), para poder comparar posiciones
    entre imágenes de distinto tamaño. Devuelve estadísticas ya calculadas
    (media, mediana, dispersión, percentiles), listas para visualizar sin
    tener que recalcularlas en cada request (pedido explícito de CAL 07)."""
    images_by_id = {image.id: image for image in dataset.images}

    all_centers: list[tuple[float, float]] = []
    centers_by_category: dict[int, list[tuple[float, float]]] = {}

    for annotation in dataset.annotations:
        image = images_by_id.get(annotation.image_id)
        if image is None:
            continue
        x, y, width, height = annotation.bbox
        center = ((x + width / 2) / image.width, (y + height / 2) / image.height)
        all_centers.append(center)
        centers_by_category.setdefault(annotation.category_id, []).append(center)

    return SpatialBiasReport(
        threshold=config.threshold,
        severity=config.severity,
        global_stats=_compute_stats(all_centers),
        stats_by_category={
            category_id: _compute_stats(centers)
            for category_id, centers in centers_by_category.items()
        },
    )
