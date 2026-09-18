from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.models.coco import CocoDataset
from dataset_quality.models.config import CheckConfig

# Imagen de 100x100. 4 cajas de "car", todas con y=0, height=20 (centro_y
# siempre en 10/100=0.1), y centro_x en 0.1, 0.3, 0.7, 0.9 — números
# redondos, fáciles de verificar a mano.
#
# xs ordenados: [0.1, 0.3, 0.7, 0.9]
#   media = (0.1+0.3+0.7+0.9)/4 = 0.5
#   mediana = (0.3+0.7)/2 = 0.5
#   desviación estándar poblacional: desvíos -0.4,-0.2,0.2,0.4 ->
#     cuadrados 0.16,0.04,0.04,0.16 -> suma 0.4 -> /4=0.1 -> sqrt=0.31622...
#   p25 (rango más cercano, índice ceil(0.25*4)-1=0) = 0.1
#   p75 (índice ceil(0.75*4)-1=2) = 0.7
#
# ys: todos 0.1 -> media=mediana=0.1, std=0.

CATEGORY_ID = 1
IMAGE_ID = 1


def _annotation(annotation_id: int, x: float, width: float) -> dict:
    return {
        "id": annotation_id,
        "image_id": IMAGE_ID,
        "category_id": CATEGORY_ID,
        "bbox": [x, 0, width, 20],
        "area": width * 20,
        "iscrowd": 0,
    }


def _build_dataset() -> CocoDataset:
    return CocoDataset.model_validate(
        {
            "images": [{"id": IMAGE_ID, "file_name": "a.jpg", "width": 100, "height": 100}],
            "categories": [{"id": CATEGORY_ID, "name": "car"}],
            "annotations": [
                _annotation(1, 0, 20),  # centro_x = (0+10)/100 = 0.1
                _annotation(2, 20, 20),  # centro_x = (20+10)/100 = 0.3
                _annotation(3, 60, 20),  # centro_x = (60+10)/100 = 0.7
                _annotation(4, 80, 20),  # centro_x = (80+10)/100 = 0.9
            ],
        }
    )


def test_computes_mean_and_median_correctly() -> None:
    report = analyze_spatial_bias(_build_dataset(), CheckConfig(threshold=0.5, severity="warn"))

    assert report.global_stats.mean_x == 0.5
    assert report.global_stats.median_x == 0.5
    assert round(report.global_stats.mean_y, 4) == 0.1
    assert round(report.global_stats.median_y, 4) == 0.1


def test_computes_standard_deviation_correctly() -> None:
    report = analyze_spatial_bias(_build_dataset(), CheckConfig(threshold=0.5, severity="warn"))

    assert round(report.global_stats.std_x, 4) == round(0.4**0.5 / 2, 4)  # sqrt(0.1) ≈ 0.3162
    assert report.global_stats.std_y == 0.0


def test_computes_percentiles_correctly() -> None:
    report = analyze_spatial_bias(_build_dataset(), CheckConfig(threshold=0.5, severity="warn"))

    assert report.global_stats.p25_x == 0.1
    assert report.global_stats.p75_x == 0.7


def test_reports_stats_by_category() -> None:
    report = analyze_spatial_bias(_build_dataset(), CheckConfig(threshold=0.5, severity="warn"))

    assert CATEGORY_ID in report.stats_by_category
    assert report.stats_by_category[CATEGORY_ID].count == 4
    assert report.stats_by_category[CATEGORY_ID].mean_x == 0.5


def test_empty_dataset_does_not_crash() -> None:
    empty_dataset = CocoDataset.model_validate({"images": [], "annotations": [], "categories": []})
    report = analyze_spatial_bias(empty_dataset, CheckConfig(threshold=0.5, severity="warn"))

    assert report.global_stats.count == 0
    assert report.stats_by_category == {}
