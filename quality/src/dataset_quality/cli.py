import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.adapters.phash import compute_phash
from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.models.coco import CocoDataset
from dataset_quality.policy.quality_gate import evaluate_quality_gate

# Código de salida reservado para errores de EJECUCIÓN (ej. falta un
# archivo de imagen) — distinto del 1, que significa "el Quality Gate
# corrió bien y el dataset falló una regla de calidad real". Mezclar
# ambos casos bajo el mismo código haría imposible distinguir "algo está
# roto en mis inputs" de "el dataset genuinamente no pasa".
EXIT_CODE_EXECUTION_ERROR = 2


def _compute_image_hashes(dataset: CocoDataset, images_dir: Path) -> dict[int, str] | None:
    """Resuelve cada image.file_name contra images_dir y calcula su pHash
    real. Devuelve None (en vez de lanzar) si falta algún archivo, para que
    main() pueda reportar el error e imprimir un exit code distinto sin
    que esta función mezcle E/S de terminal con la orquestación."""
    hashes: dict[int, str] = {}
    for image in dataset.images:
        image_path = images_dir / image.file_name
        if not image_path.exists():
            print(
                f"Error: no se encontró la imagen '{image.file_name}' "
                f"(image_id={image.id}) en {images_dir}",
                file=sys.stderr,
            )
            return None
        hashes[image.id] = compute_phash(image_path)
    return hashes


def _load_dataset(coco_path: Path) -> CocoDataset | None:
    """Carga y valida el COCO. Devuelve None (en vez de dejar escapar el
    traceback de Pydantic) si el archivo no existe, no es JSON válido, o
    no cumple el esquema — para que main() pueda reportar el error con
    un mensaje legible y un exit code distinto del 1 (que significa "el
    Quality Gate corrió bien y el dataset falló una regla de calidad
    real"). Mismo patrón que _compute_image_hashes."""
    try:
        with coco_path.open("r", encoding="utf-8") as file:
            raw_coco = json.load(file)
        return CocoDataset.model_validate(raw_coco)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Error: no se pudo leer '{coco_path}': {error}", file=sys.stderr)
        return None
    except ValidationError as error:
        print(f"Error: el COCO en '{coco_path}' no es válido:", file=sys.stderr)
        for issue in error.errors():
            field = ".".join(str(part) for part in issue["loc"])
            print(f"  - {field}: {issue['msg']}", file=sys.stderr)
        return None


def run_quality_gate(
    coco_path: Path, quality_config_path: Path, images_dir: Path, output_path: Path | None
) -> int:
    """Orquesta: carga quality.yaml + el COCO, calcula pHash real de cada
    imagen, corre los 5 analizadores + el Quality Gate, escribe el
    reporte, y devuelve el exit code."""
    config = load_quality_config(quality_config_path)

    dataset = _load_dataset(coco_path)
    if dataset is None:
        return EXIT_CODE_EXECUTION_ERROR

    image_hashes = _compute_image_hashes(dataset, images_dir)
    if image_hashes is None:
        return EXIT_CODE_EXECUTION_ERROR

    small_objects = analyze_small_objects(dataset, config.checks["small_objects"])
    class_imbalance = analyze_class_imbalance(
        dataset,
        config.checks["class_imbalance"],
        min_images_threshold=config.checks["min_images_per_class"].threshold,
    )
    duplicates = analyze_duplicates(image_hashes, config.checks["duplicates"])
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
        "--images-dir",
        type=Path,
        required=True,
        help="Carpeta con los archivos de imagen reales (para calcular pHash).",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Ruta donde escribir quality.json (opcional)."
    )
    args = parser.parse_args()

    exit_code = run_quality_gate(args.coco, args.config, args.images_dir, args.output)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
