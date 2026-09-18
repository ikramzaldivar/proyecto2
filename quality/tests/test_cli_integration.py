import json
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw


def _write_coco(path: Path, image_file_names: list[str]) -> None:
    images = [
        {"id": i + 1, "file_name": name, "width": 200, "height": 200}
        for i, name in enumerate(image_file_names)
    ]
    annotations = [
        {
            "id": i + 1,
            "image_id": i + 1,
            "category_id": 1 if i % 2 == 0 else 2,
            "bbox": [10, 10, 20, 20],
            "area": 400,
            "iscrowd": 0,
        }
        for i in range(len(image_file_names))
    ]
    coco = {
        "images": images,
        "categories": [{"id": 1, "name": "car"}, {"id": 2, "name": "person"}],
        "annotations": annotations,
    }
    path.write_text(json.dumps(coco), encoding="utf-8")


def _write_quality_config(
    path: Path, min_images_threshold: float, duplicates_severity: str = "warn"
) -> None:
    config = {
        "checks": {
            "min_images_per_class": {
                "threshold": min_images_threshold,
                "min_classes": 2,
                "severity": "fail",
            },
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {"threshold": 10, "severity": "warn"},
            "duplicates": {"threshold": 8, "severity": duplicates_severity},
            "invalid_boxes": {"threshold": 0, "severity": "fail"},
            "spatial_bias": {"threshold": 0.5, "severity": "warn"},
        },
        "splits": {"train": 0.7, "val": 0.15, "test": 0.15, "seed": 42},
    }
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def _make_real_image() -> Image.Image:
    image = Image.new("RGB", (200, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, 100, 100], fill=(255, 0, 0))
    draw.ellipse([100, 100, 180, 180], fill=(0, 0, 255))
    return image


def _run_cli(
    coco_path: Path, config_path: Path, images_dir: Path, output_path: Path | None = None
) -> subprocess.CompletedProcess:
    args = [
        sys.executable,
        "-m",
        "dataset_quality.cli",
        "--coco",
        str(coco_path),
        "--config",
        str(config_path),
        "--images-dir",
        str(images_dir),
    ]
    if output_path is not None:
        args += ["--output", str(output_path)]
    return subprocess.run(args, capture_output=True, text=True, check=False)


def test_cli_exits_with_code_1_on_impossible_threshold(tmp_path: Path) -> None:
    # CAL 08, criterio de cierre ejecutable: "un mínimo imposible hace fallar el comando".
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    _write_coco(coco_path, ["img1.png", "img2.png"])
    _write_quality_config(config_path, min_images_threshold=1000)
    _make_real_image().save(images_dir / "img1.png")
    _make_real_image().save(images_dir / "img2.png")

    process = _run_cli(coco_path, config_path, images_dir)

    assert process.returncode == 1


def test_cli_exits_with_code_0_when_threshold_is_restored(tmp_path: Path) -> None:
    # CAL 08, criterio de cierre ejecutable: "restaurar el umbral produce PASS".
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    _write_coco(coco_path, ["img1.png", "img2.png"])
    _write_quality_config(config_path, min_images_threshold=1)
    _make_real_image().save(images_dir / "img1.png")
    _make_real_image().save(images_dir / "img2.png")

    process = _run_cli(coco_path, config_path, images_dir)

    assert process.returncode == 0


def test_cli_writes_a_valid_quality_json_report(tmp_path: Path) -> None:
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    output_path = tmp_path / "quality.json"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    _write_coco(coco_path, ["img1.png", "img2.png"])
    _write_quality_config(config_path, min_images_threshold=1)
    _make_real_image().save(images_dir / "img1.png")
    _make_real_image().save(images_dir / "img2.png")

    _run_cli(coco_path, config_path, images_dir, output_path=output_path)

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["overall_status"] == "pass"
    assert len(report["checks"]) == 6


def test_cli_detects_real_duplicate_images_with_the_configured_severity(tmp_path: Path) -> None:
    # CAL 08 (corrección del PM): dos imágenes visualmente equivalentes de
    # verdad deben aparecer como grupo duplicado en el reporte, con la
    # severidad configurada aplicada — no un reporte vacío de duplicados.
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    output_path = tmp_path / "quality.json"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    _write_coco(coco_path, ["original.png", "recompressed.jpg"])
    _write_quality_config(config_path, min_images_threshold=1, duplicates_severity="warn")

    base = _make_real_image()
    base.save(images_dir / "original.png")
    base.save(images_dir / "recompressed.jpg", "JPEG", quality=30)

    process = _run_cli(coco_path, config_path, images_dir, output_path=output_path)

    assert process.returncode == 0  # duplicates es "warn", no bloquea
    report = json.loads(output_path.read_text(encoding="utf-8"))
    duplicates_check = next(c for c in report["checks"] if c["name"] == "duplicates")
    assert duplicates_check["status"] == "warn"
    assert duplicates_check["observed"]["group_count"] >= 1


def test_cli_fails_clearly_when_an_image_file_is_missing(tmp_path: Path) -> None:
    # CAL 08 (corrección del PM): imagen referenciada en el COCO pero
    # ausente del directorio -> error explícito y no-cero, NUNCA un
    # reporte incompleto silencioso.
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    _write_coco(coco_path, ["exists.png", "missing.png"])
    _write_quality_config(config_path, min_images_threshold=1)
    _make_real_image().save(images_dir / "exists.png")
    # "missing.png" nunca se crea a propósito.

    process = _run_cli(coco_path, config_path, images_dir)

    assert process.returncode not in (0, 1)  # distinto de un resultado de gate normal
    assert "missing.png" in process.stderr
