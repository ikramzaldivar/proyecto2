"""Etapa 3 del pipeline: compuerta de calidad, splits y release.json.

Esto es ORQUESTACION, no logica de calidad. Toda la decision vive en
`dataset_quality`: la compuerta en `policy.quality_gate`, los splits en
`splits.generator`, la verificacion de fuga en `splits.report` y los
conteos de CAL 10 en `policy.class_counts` / `policy.reannotation_queue`.
Aqui solo se leen artefactos, se llaman esas funciones en orden y se arma
el documento.

La forma exacta de release.json es `releaseBundleSchema` en
`backend/src/logic/quality/contracts.ts`: el portal lo valida con Zod y
rechaza ruidosamente cualquier campo que no cuadre.

Sobre el exit code: si la compuerta falla, release.json SE ESCRIBE de
todas formas, con `quality.overall_status = "fail"` adentro, y despues el
proceso sale con codigo 1. Asi queda la evidencia en disco para poder
diagnosticar por que fallo, pero DVC marca la etapa como fallida y NO
registra el out en dvc.lock: no hay release nuevo, solo el reporte de por
que no lo hubo.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.analyzers.class_imbalance import ClassImbalanceReport
from dataset_quality.analyzers.duplicates import DuplicatesReport
from dataset_quality.analyzers.invalid_boxes import InvalidBoxesReport
from dataset_quality.analyzers.small_objects import SmallObjectsReport
from dataset_quality.analyzers.spatial_bias import SpatialBiasReport
from dataset_quality.models.coco import CocoDataset
from dataset_quality.policy.class_counts import count_distinct_images_before_and_after_duplicates
from dataset_quality.policy.quality_gate import evaluate_quality_gate
from dataset_quality.policy.reannotation_queue import build_reannotation_queue
from dataset_quality.splits.generator import generate_splits
from dataset_quality.splits.report import build_leakage_report, build_split_distribution

SCHEMA_VERSION = 1

DEFAULT_DATASET_VERSION = "v0.0.0-dev"

# El orden importa: es el que espera evaluate_quality_gate() por posicion.
ANALYZER_MODELS = {
    "small_objects": SmallObjectsReport,
    "class_imbalance": ClassImbalanceReport,
    "duplicates": DuplicatesReport,
    "invalid_boxes": InvalidBoxesReport,
    "spatial_bias": SpatialBiasReport,
}


def load_analyzer_reports(analyzers_dir: Path) -> dict:
    """Reconstruye los 5 modelos Pydantic desde los JSON que dejo la etapa
    `analyze`. Si a alguno le falta un campo, Pydantic revienta aqui — que
    es lo que queremos: mejor romper que armar un release a medias."""
    reports = {}
    for name, model in ANALYZER_MODELS.items():
        path = analyzers_dir / f"{name}.json"
        if not path.exists():
            raise SystemExit(f"falta el reporte del analizador: {path}")
        reports[name] = model.model_validate_json(path.read_text(encoding="utf-8"))
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Arma release.json y corre el Quality Gate.")
    parser.add_argument("--coco", required=True, type=Path, help="Export COCO del portal")
    parser.add_argument("--config", required=True, type=Path, help="quality.yaml")
    parser.add_argument(
        "--analyzers-dir",
        required=True,
        type=Path,
        help="Carpeta con los 5 JSON que escribio la etapa analyze",
    )
    parser.add_argument("--out", required=True, type=Path, help="Ruta de salida de release.json")
    parser.add_argument(
        "--dataset-version",
        default=os.environ.get("DATASET_VERSION", DEFAULT_DATASET_VERSION),
        help=(
            "Version semantica del dataset. Por defecto toma la variable de entorno "
            f"DATASET_VERSION, y si tampoco esta, {DEFAULT_DATASET_VERSION}."
        ),
    )
    args = parser.parse_args()

    config = load_quality_config(args.config)
    dataset = CocoDataset.model_validate_json(args.coco.read_text(encoding="utf-8"))
    reports = load_analyzer_reports(args.analyzers_dir)

    gate = evaluate_quality_gate(
        config,
        reports["small_objects"],
        reports["class_imbalance"],
        reports["duplicates"],
        reports["invalid_boxes"],
        reports["spatial_bias"],
    )

    duplicate_groups = reports["duplicates"].duplicate_groups

    assignment = generate_splits(dataset, duplicate_groups, config.splits)
    distribution = build_split_distribution(dataset, assignment)
    leakage = build_leakage_report(dataset, assignment, duplicate_groups, distribution)

    class_counts = count_distinct_images_before_and_after_duplicates(dataset, duplicate_groups)
    reannotation_queue = build_reannotation_queue(reports["invalid_boxes"])

    release = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": args.dataset_version,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "seed": config.splits.seed,
        "totals": {
            "images": len(dataset.images),
            "annotations": len(dataset.annotations),
            "categories": len(dataset.categories),
        },
        "categories": [
            {"id": category.id, "name": category.name} for category in dataset.categories
        ],
        "quality": gate.model_dump(mode="json"),
        "analyzers": {name: report.model_dump(mode="json") for name, report in reports.items()},
        "class_counts": [comparison.model_dump(mode="json") for comparison in class_counts],
        "splits": {
            "seed": config.splits.seed,
            "proportions": {
                "train": config.splits.train,
                "val": config.splits.val,
                "test": config.splits.test,
            },
            "assignment": assignment.model_dump(mode="json"),
            "distribution": [entry.model_dump(mode="json") for entry in distribution],
            "leakage": leakage.model_dump(mode="json"),
        },
        "reannotation_queue": [item.model_dump(mode="json") for item in reannotation_queue],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")

    print(f"release {args.dataset_version} -> {args.out}")
    print(f"quality gate: {gate.overall_status} (exit code {gate.exit_code})")
    for check in gate.checks:
        if check.status != "pass":
            print(f"  {check.status}: {check.name} {check.observed}")
    print(
        "splits: "
        + ", ".join(f"{entry.split}={entry.total_images}" for entry in distribution)
        + f" | fuga: ids={leakage.id_intersection_size} "
        + f"pares_cruzados={leakage.cross_split_duplicate_pairs}"
    )

    raise SystemExit(gate.exit_code)


if __name__ == "__main__":
    main()
