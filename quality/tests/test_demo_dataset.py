import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.adapters.phash import compute_phash
from dataset_quality.analyzers.class_imbalance import analyze_class_imbalance
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.analyzers.invalid_boxes import analyze_invalid_boxes
from dataset_quality.analyzers.small_objects import analyze_small_objects
from dataset_quality.analyzers.spatial_bias import analyze_spatial_bias
from dataset_quality.demo.synthetic import build_demo_dataset, render_demo_image
from dataset_quality.models.coco import CocoDataset
from dataset_quality.policy.quality_gate import evaluate_quality_gate
from dataset_quality.splits.generator import generate_splits
from dataset_quality.splits.report import build_leakage_report, build_split_distribution

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_CONFIG = REPO_ROOT / "quality" / "quality.demo.yaml"
REAL_CONFIG = REPO_ROOT / "quality" / "quality.yaml"
SCRIPT = REPO_ROOT / "pipeline" / "make_demo_dataset.py"


@pytest.fixture(scope="module")
def demo():
    return build_demo_dataset(seed=7, image_count=40)


@pytest.fixture(scope="module")
def analyzed(demo, tmp_path_factory):
    """Renderiza las imágenes, calcula pHash y corre los cinco analizadores."""
    images_dir = tmp_path_factory.mktemp("demo-images")
    dataset = CocoDataset.model_validate(demo.coco)
    hashes: dict[int, str] = {}
    for spec, image in zip(demo.images, dataset.images, strict=True):
        path = images_dir / spec.file_name
        render_demo_image(spec).save(path, quality=spec.jpeg_quality)
        hashes[image.id] = compute_phash(path)

    config = load_quality_config(DEMO_CONFIG)
    small = analyze_small_objects(dataset, config.checks["small_objects"])
    imbalance = analyze_class_imbalance(
        dataset,
        config.checks["class_imbalance"],
        int(config.checks["min_images_per_class"].threshold),
    )
    duplicates = analyze_duplicates(hashes, config.checks["duplicates"])
    invalid = analyze_invalid_boxes(dataset, config.checks["invalid_boxes"])
    spatial = analyze_spatial_bias(dataset, config.checks["spatial_bias"])
    gate = evaluate_quality_gate(config, small, imbalance, duplicates, invalid, spatial)
    return {
        "dataset": dataset,
        "config": config,
        "small": small,
        "duplicates": duplicates,
        "invalid": invalid,
        "gate": gate,
    }


def test_the_dataset_is_deterministic_for_a_given_seed() -> None:
    first = build_demo_dataset(seed=7, image_count=40)
    second = build_demo_dataset(seed=7, image_count=40)
    other = build_demo_dataset(seed=8, image_count=40)

    assert first.coco == second.coco
    assert first.coco != other.coco


def test_it_is_a_valid_coco_with_the_requested_number_of_images(demo) -> None:
    dataset = CocoDataset.model_validate(demo.coco)

    assert len(dataset.images) == 40 == len(demo.images)
    assert {category.name for category in dataset.categories} == {"person", "car", "dog"}


def test_every_class_is_present_and_at_least_two_reach_the_demo_minimum(demo) -> None:
    dataset = CocoDataset.model_validate(demo.coco)
    images_by_class: dict[int, set[int]] = {}
    for annotation in dataset.annotations:
        images_by_class.setdefault(annotation.category_id, set()).add(annotation.image_id)

    minimum = int(load_quality_config(DEMO_CONFIG).checks["min_images_per_class"].threshold)

    assert len(images_by_class) == 3
    assert sum(1 for images in images_by_class.values() if len(images) >= minimum) >= 2


def test_the_demo_policy_is_looser_than_the_real_one_and_says_so() -> None:
    demo_min = load_quality_config(DEMO_CONFIG).checks["min_images_per_class"].threshold
    real_min = load_quality_config(REAL_CONFIG).checks["min_images_per_class"].threshold

    assert real_min == 300
    assert demo_min < real_min
    assert "SOLO DEMO" in DEMO_CONFIG.read_text(encoding="utf-8")


def test_the_demo_release_passes_the_gate(analyzed) -> None:
    assert analyzed["gate"].overall_status == "pass"
    assert analyzed["gate"].exit_code == 0


def test_there_is_exactly_one_near_duplicate_pair_and_it_is_the_planted_one(
    demo, analyzed
) -> None:
    dataset = analyzed["dataset"]
    id_of = {image.file_name: image.id for image in dataset.images}
    planted = [spec for spec in demo.images if spec.duplicate_of is not None]

    assert len(planted) == 1
    expected = {id_of[planted[0].file_name], id_of[planted[0].duplicate_of]}
    found = [
        {pair.image_id_a, pair.image_id_b}
        for pair in analyzed["duplicates"].pairs
    ]
    assert found == [expected]


def test_it_has_small_objects_and_no_invalid_boxes(analyzed) -> None:
    assert analyzed["small"].small_count >= 1
    assert analyzed["invalid"].invalid_count == 0


def test_splits_keep_every_class_in_val_and_test_without_leakage(analyzed) -> None:
    dataset = analyzed["dataset"]
    groups = analyzed["duplicates"].duplicate_groups
    assignment = generate_splits(dataset, groups, analyzed["config"].splits)
    distribution = build_split_distribution(dataset, assignment)
    leakage = build_leakage_report(dataset, assignment, groups, distribution)

    assert leakage.all_classes_in_val and leakage.all_classes_in_test
    assert leakage.id_intersection_size == 0
    assert leakage.cross_split_duplicate_pairs == 0


def test_the_script_writes_the_images_and_a_coco_that_matches_them(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path / "demo")],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "quality" / "src")},
    )

    assert result.returncode == 0, result.stderr
    coco = json.loads((tmp_path / "demo" / "coco.json").read_text(encoding="utf-8"))
    written = sorted(path.name for path in (tmp_path / "demo" / "images").iterdir())
    assert written == sorted(image["file_name"] for image in coco["images"])
    assert len(written) == 40
