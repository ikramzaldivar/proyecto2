import json
import subprocess
import sys
from pathlib import Path

import yaml


def _write_coco(path: Path) -> None:
    coco = {
        "images": [
            {"id": 1, "file_name": "img1.jpg", "width": 100, "height": 100},
            {"id": 2, "file_name": "img2.jpg", "width": 100, "height": 100},
        ],
        "categories": [{"id": 1, "name": "car"}, {"id": 2, "name": "person"}],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            },
            {
                "id": 2,
                "image_id": 2,
                "category_id": 2,
                "bbox": [10, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            },
        ],
    }
    path.write_text(json.dumps(coco), encoding="utf-8")


def _write_quality_config(path: Path, min_images_threshold: float) -> None:
    config = {
        "checks": {
            "min_images_per_class": {
                "threshold": min_images_threshold,
                "min_classes": 2,
                "severity": "fail",
            },
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {"threshold": 10, "severity": "warn"},
            "duplicates": {"threshold": 8, "severity": "warn"},
            "invalid_boxes": {"threshold": 0, "severity": "fail"},
            "spatial_bias": {"threshold": 0.5, "severity": "warn"},
        },
        "splits": {"train": 0.7, "val": 0.15, "test": 0.15, "seed": 42},
    }
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def _run_cli(coco_path: Path, config_path: Path) -> subprocess.CompletedProcess:
    # Invoca el módulo real como proceso aparte (no una llamada de función
    # dentro del mismo proceso de pytest) — así se prueba el entrypoint de
    # verdad, incluyendo raise SystemExit(...) y el código de salida real
    # del proceso del sistema operativo.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "dataset_quality.cli",
            "--coco",
            str(coco_path),
            "--config",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exits_with_code_1_on_impossible_threshold(tmp_path: Path) -> None:
    # CAL 08, criterio de cierre ejecutable: "un mínimo imposible hace
    # fallar el comando" — probado invocando el comando real, no solo
    # afirmando result.exit_code en memoria.
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    _write_coco(coco_path)
    _write_quality_config(config_path, min_images_threshold=1000)

    process = _run_cli(coco_path, config_path)

    assert process.returncode == 1


def test_cli_exits_with_code_0_when_threshold_is_restored(tmp_path: Path) -> None:
    # CAL 08, criterio de cierre ejecutable: "restaurar el umbral produce PASS".
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    _write_coco(coco_path)
    _write_quality_config(config_path, min_images_threshold=1)

    process = _run_cli(coco_path, config_path)

    assert process.returncode == 0


def test_cli_writes_a_valid_quality_json_report(tmp_path: Path) -> None:
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    output_path = tmp_path / "quality.json"
    _write_coco(coco_path)
    _write_quality_config(config_path, min_images_threshold=1)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "dataset_quality.cli",
            "--coco",
            str(coco_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["overall_status"] == "pass"
    assert len(report["checks"]) == 6
