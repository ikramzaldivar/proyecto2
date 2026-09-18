import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "pipeline" / "register_version.py"
SRC = REPO_ROOT / "quality" / "src"


def _release(overall_status: str = "pass") -> dict:
    return {
        "generated_at": "2026-09-18T19:58:20.988152Z",
        "quality": {"overall_status": overall_status},
        "totals": {"images": 689, "annotations": 1455, "categories": 3},
        "analyzers": {
            "small_objects": {"small_percent": 0.41},
            "class_imbalance": {"ratio": 5.93},
            "duplicates": {"duplicate_groups": [[1, 2]]},
            "invalid_boxes": {"invalid_count": 0},
        },
        "class_counts": [
            {"category_id": 1, "distinct_images_before": 421, "distinct_images_after": 421},
            {"category_id": 2, "distinct_images_before": 400, "distinct_images_after": 399},
        ],
    }


def _config(path: Path, threshold: float = 300) -> None:
    config = {
        "checks": {
            "min_images_per_class": {"threshold": threshold, "min_classes": 2, "severity": "fail"},
            "small_objects": {"threshold": 32, "severity": "warn"},
            "class_imbalance": {"threshold": 10, "severity": "warn"},
            "duplicates": {"threshold": 8, "severity": "warn"},
            "invalid_boxes": {"threshold": 0, "severity": "fail"},
            "spatial_bias": {"threshold": 0.5, "severity": "warn"},
        },
        "splits": {"train": 0.7, "val": 0.15, "test": 0.15, "seed": 42},
    }
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def _run(tmp_path: Path, version: str, release: dict | None = None, extra: list[str] | None = None):
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(release or _release()), encoding="utf-8")
    config_path = tmp_path / "quality.yaml"
    _config(config_path)

    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release_path),
            "--config",
            str(config_path),
            "--registry",
            str(tmp_path / "versions.json"),
            "--version",
            version,
            "--commit",
            "abc1234",
            "--dvc-revision",
            "2ae957bd",
            *(extra or []),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )


def test_creates_versions_json_with_the_course_minimum(tmp_path: Path) -> None:
    result = _run(tmp_path, "v1.0.0")

    assert result.returncode == 0, result.stderr
    registry = json.loads((tmp_path / "versions.json").read_text(encoding="utf-8"))
    assert registry["minimumImagesPerClass"] == 300
    assert [v["version"] for v in registry["versions"]] == ["v1.0.0"]
    assert registry["versions"][0]["commit"] == "abc1234"
    assert registry["versions"][0]["classCounts"][1] == {"categoryId": 2, "distinctImages": 399}


def test_a_second_run_appends_and_keeps_the_history(tmp_path: Path) -> None:
    assert _run(tmp_path, "v1.0.0").returncode == 0
    assert _run(tmp_path, "v1.1.0").returncode == 0

    registry = json.loads((tmp_path / "versions.json").read_text(encoding="utf-8"))
    assert [v["version"] for v in registry["versions"]] == ["v1.0.0", "v1.1.0"]
    assert registry["versions"][1]["parentVersion"] == "v1.0.0"


def test_environment_hashes_mark_the_version_as_pushed(tmp_path: Path) -> None:
    result = _run(tmp_path, "v1.0.0", extra=["--dev-hash", "2ae957bd", "--prod-hash", "2ae957bd"])

    assert result.returncode == 0, result.stderr
    registry = json.loads((tmp_path / "versions.json").read_text(encoding="utf-8"))
    environments = registry["versions"][0]["environments"]
    assert environments["dev"] == {"status": "pushed", "contentHash": "2ae957bd"}
    assert environments["prod"] == {"status": "pushed", "contentHash": "2ae957bd"}


@pytest.mark.parametrize("bad_version", ["1.0.0", "v1.0", "v0.0.0-dev"])
def test_a_non_semantic_version_is_rejected_and_nothing_is_written(
    tmp_path: Path, bad_version: str
) -> None:
    result = _run(tmp_path, bad_version)

    assert result.returncode != 0
    assert "versión semántica" in result.stderr
    assert not (tmp_path / "versions.json").exists()


def test_a_release_whose_gate_failed_cannot_become_a_version(tmp_path: Path) -> None:
    result = _run(tmp_path, "v1.0.0", release=_release("fail"))

    assert result.returncode != 0
    assert "compuerta" in result.stderr
    assert not (tmp_path / "versions.json").exists()
