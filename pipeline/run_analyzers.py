"""Etapa 2 del pipeline: corre los cinco analizadores sobre el export COCO.

Esto es ORQUESTACION, no logica de calidad. No implementa ningun check ni
decide si el dataset pasa o no: solo carga `quality.yaml` con el loader
existente, valida el COCO con `CocoDataset` y llama a las funciones puras de
`dataset_quality.analyzers`, guardando cada reporte tal cual lo devuelven.

La compuerta (pass/fail, CAL 08) NO vive aqui: le corresponde al modulo
`dataset_quality.policy` y la corre la etapa `release` (pipeline/build_release.py).

Si alguna imagen del COCO no trae pHash, esta etapa se DETIENE con exit code
distinto de cero en vez de solo avisar: el analisis de duplicados sobre un
subconjunto de las imagenes da un resultado que parece valido y no lo es, y
ese resultado alimenta tanto la compuerta como los splits.
"""

import argparse
import json
import sys
from pathlib import Path

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.cli import EXIT_CODE_EXECUTION_ERROR
from dataset_quality.models.coco import CocoDataset


def build_image_hashes(
    dataset: CocoDataset, hashes: dict[str, str]
) -> tuple[dict[int, str], int]:
    """Traduce {ruta relativa -> pHash} a {image_id -> pHash}, que es lo que
    espera `analyze_duplicates`. El `file_name` del COCO puede venir con o sin
    carpeta, asi que se intenta primero la ruta exacta y luego el nombre de
    archivo solo."""
    by_basename = {Path(key).name: value for key, value in hashes.items()}

    image_hashes: dict[int, str] = {}
    missing = 0
    for image in dataset.images:
        digest = hashes.get(image.file_name) or by_basename.get(
            Path(image.file_name).name
        )
        if digest is None:
            missing += 1
            continue
        image_hashes[image.id] = digest

    return image_hashes, missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coco", required=True, type=Path, help="Export COCO del portal"
    )
    parser.add_argument("--config", required=True, type=Path, help="quality.yaml")
    parser.add_argument(
        "--hashes", required=True, type=Path, help="Salida de hash_images.py"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Carpeta base de reportes"
    )
    args = parser.parse_args()

    config = load_quality_config(args.config)
    dataset = CocoDataset.model_validate_json(args.coco.read_text(encoding="utf-8"))
    hashes = json.loads(args.hashes.read_text(encoding="utf-8"))["hashes"]

    image_hashes, images_without_hash = build_image_hashes(dataset, hashes)
    if images_without_hash:
        print(
            f"Error: {images_without_hash} de {len(dataset.images)} imagenes del COCO no tienen "
            f"pHash en {args.hashes}. Sin ellas el analisis de duplicados quedaria incompleto y "
            "arrastraria a la compuerta y a los splits, asi que la etapa se detiene. Revisa que "
            "data/raw/images tenga todas las imagenes del export (dvc pull) y vuelve a correr.",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_EXECUTION_ERROR)

    min_images = config.checks["min_images_per_class"]

    reports = {
        "small_objects": analyze_small_objects(dataset, config.checks["small_objects"]),
        "class_imbalance": analyze_class_imbalance(
            dataset, config.checks["class_imbalance"], int(min_images.threshold)
        ),
        "invalid_boxes": analyze_invalid_boxes(dataset, config.checks["invalid_boxes"]),
        "spatial_bias": analyze_spatial_bias(dataset, config.checks["spatial_bias"]),
        "duplicates": analyze_duplicates(image_hashes, config.checks["duplicates"]),
    }

    reports_dir = args.out / "analyzers"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        (reports_dir / f"{name}.json").write_text(
            report.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )

    # metrics.json se versiona en git (cache: false en dvc.yaml): es el
    # resumen chico y diffeable que `dvc metrics diff` compara entre releases.
    metrics = {
        "dataset": {
            "images": len(dataset.images),
            "annotations": len(dataset.annotations),
            "categories": len(dataset.categories),
            "images_with_phash": len(image_hashes),
            "images_without_phash": images_without_hash,
        },
        "small_objects": {
            "small_count": reports["small_objects"].small_count,
            "small_percent": round(reports["small_objects"].small_percent, 4),
        },
        "class_imbalance": {
            "ratio": reports["class_imbalance"].ratio,
            "classes_below_min_images": len(
                reports["class_imbalance"].classes_below_min_images
            ),
        },
        "invalid_boxes": {
            "invalid_count": reports["invalid_boxes"].invalid_count,
        },
        "duplicates": {
            "pairs": len(reports["duplicates"].pairs),
            "groups": len(reports["duplicates"].duplicate_groups),
        },
        "spatial_bias": {
            "mean_x": round(reports["spatial_bias"].global_stats.mean_x, 4),
            "mean_y": round(reports["spatial_bias"].global_stats.mean_y, 4),
            "std_x": round(reports["spatial_bias"].global_stats.std_x, 4),
            "std_y": round(reports["spatial_bias"].global_stats.std_y, 4),
        },
    }

    (args.out / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"{len(reports)} reportes en {reports_dir} y resumen en {args.out / 'metrics.json'}"
    )


if __name__ == "__main__":
    main()
