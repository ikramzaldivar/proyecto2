import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
HASH_SCRIPT = REPO_ROOT / "pipeline" / "hash_images.py"
ANALYZE_SCRIPT = REPO_ROOT / "pipeline" / "run_analyzers.py"
RELEASE_SCRIPT = REPO_ROOT / "pipeline" / "build_release.py"
SRC = REPO_ROOT / "quality" / "src"


def _write_coco(path: Path) -> None:
    images = [
        {"id": i + 1, "file_name": f"img{i + 1}.png", "width": 200, "height": 200} for i in range(2)
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
        for i in range(2)
    ]
    coco = {
        "images": images,
        "categories": [{"id": 1, "name": "car"}, {"id": 2, "name": "person"}],
        "annotations": annotations,
    }
    path.write_text(json.dumps(coco), encoding="utf-8")


def _write_quality_config(path: Path) -> None:
    config = {
        "checks": {
            "min_images_per_class": {"threshold": 1, "min_classes": 2, "severity": "fail"},
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {"threshold": 10, "severity": "warn"},
            "duplicates": {"threshold": 8, "severity": "warn"},
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
    return image


def _run(*args: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, env=env, check=False
    )


def test_cli_flag_takes_precedence_over_dataset_version_env_var(tmp_path: Path) -> None:
    # C-12: --dataset-version explícito debe ganar sobre la variable de
    # entorno DATASET_VERSION, no al revés.
    coco_path = tmp_path / "dataset.json"
    config_path = tmp_path / "quality.yaml"
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    hashes_path = tmp_path / "hashes.json"
    analyzers_dir = tmp_path / "analyzers"
    release_path = tmp_path / "release.json"

    _write_coco(coco_path)
    _write_quality_config(config_path)
    _make_real_image().save(images_dir / "img1.png")
    _make_real_image().save(images_dir / "img2.png")

    hash_result = _run(str(HASH_SCRIPT), "--images", str(images_dir), "--out", str(hashes_path))
    assert hash_result.returncode == 0, hash_result.stderr

    analyze_result = _run(
        str(ANALYZE_SCRIPT),
        "--coco",
        str(coco_path),
        "--config",
        str(config_path),
        "--hashes",
        str(hashes_path),
        "--out",
        str(analyzers_dir),
    )
    assert analyze_result.returncode == 0, analyze_result.stderr

    release_result = _run(
        str(RELEASE_SCRIPT),
        "--coco",
        str(coco_path),
        "--config",
        str(config_path),
        "--analyzers-dir",
        str(analyzers_dir / "analyzers"),
        "--out",
        str(release_path),
        "--dataset-version",
        "v9.9.9",
        extra_env={"DATASET_VERSION": "v1.0.0"},
    )
    assert release_result.returncode == 0, release_result.stderr

    release = json.loads(release_path.read_text(encoding="utf-8"))
    assert release["dataset_version"] == "v9.9.9"
