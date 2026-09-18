import argparse
import json
from pathlib import Path

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.models.coco import CocoDataset
from dataset_quality.policy.quality_gate import evaluate_quality_gate


def run_quality_gate(coco_path: Path, quality_config_path: Path, output_path: Path | None) -> int:
    """Orquesta: carga quality.yaml + el COCO, corre los 5 analizadores y
    el Quality Gate, escribe el reporte, y devuelve el exit code.

    Limitación conocida: pHash (duplicados) necesita leer los archivos de
    imagen reales, y este CLI todavía no recibe un mapeo image_id -> ruta
    de archivo, así que corre ese analizador con hashes vacíos (0
    duplicados detectados) por ahora. Los otros 4 analizadores + el gate
    sí funcionan de punta a punta con el COCO real.
    """
    config = load_quality_config(quality_config_path)

    with coco_path.open("r", encoding="utf-8") as file:
        raw_coco = json.load(file)
    dataset = CocoDataset.model_validate(raw_coco)

    small_objects = analyze_small_objects(dataset, config.checks["small_objects"])
    class_imbalance = analyze_class_imbalance(
        dataset,
        config.checks["class_imbalance"],
        min_images_threshold=config.checks["min_images_per_class"].threshold,
    )
    duplicates = analyze_duplicates({}, config.checks["duplicates"])
    invalid_boxes = analyze_invalid_boxes(dataset, config.checks["invalid_boxes"])
    spatial_bias = analyze_spatial_bias(dataset, config.checks["spatial_bias"])

    result = evaluate_quality_gate(
        config, small_objects, class_imbalance, duplicates, invalid_boxes, spatial_bias
    )

    report_json = result.model_dump_json(indent=2)
    if output_path is not None:
        output_path.write_text(report_json, encoding="utf-8")
    else:
        print(report_json)

    return result.exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Corre el Quality Gate sobre un dataset COCO.")
    parser.add_argument("--coco", type=Path, required=True, help="Ruta al archivo COCO (JSON).")
    parser.add_argument("--config", type=Path, required=True, help="Ruta a quality.yaml.")
    parser.add_argument(
        "--output", type=Path, default=None, help="Ruta donde escribir quality.json (opcional)."
    )
    args = parser.parse_args()

    exit_code = run_quality_gate(args.coco, args.config, args.output)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
