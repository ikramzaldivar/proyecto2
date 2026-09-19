from pathlib import Path

import pytest
from pydantic import ValidationError

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.models.config import (
    REQUIRED_CHECKS,
    CheckConfig,
    PipelineSettings,
    QualityConfig,
    SplitConfig,
)


def test_check_config_accepts_valid_severity() -> None:
    check = CheckConfig(threshold=300, severity="fail")
    assert check.severity == "fail"


def test_check_config_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError, match="severity"):
        CheckConfig(threshold=300, severity="critical")


def test_check_config_rejects_extra_field() -> None:
    with pytest.raises(ValidationError, match="extra"):
        CheckConfig.model_validate({"threshold": 300, "severity": "fail", "oops": True})


def _valid_checks() -> dict:
    return {name: {"threshold": 10, "severity": "warn"} for name in REQUIRED_CHECKS}


def _valid_splits() -> dict:
    return {"train": 0.7, "val": 0.15, "test": 0.15, "seed": 42}


def test_quality_config_accepts_all_required_checks() -> None:
    config = QualityConfig.model_validate({"checks": _valid_checks(), "splits": _valid_splits()})
    assert set(config.checks.keys()) == REQUIRED_CHECKS
    assert config.splits.seed == 42


def test_quality_config_rejects_missing_severity() -> None:
    checks = _valid_checks()
    del checks["min_images_per_class"]["severity"]
    payload = {"checks": checks, "splits": _valid_splits()}

    with pytest.raises(ValidationError, match="severity"):
        QualityConfig.model_validate(payload)


def test_quality_config_rejects_missing_required_check() -> None:
    checks = _valid_checks()
    del checks["spatial_bias"]
    payload = {"checks": checks, "splits": _valid_splits()}

    with pytest.raises(ValidationError, match="spatial_bias"):
        QualityConfig.model_validate(payload)


def test_quality_config_rejects_extra_field() -> None:
    payload = {"checks": _valid_checks(), "splits": _valid_splits(), "oops": True}
    with pytest.raises(ValidationError, match="extra"):
        QualityConfig.model_validate(payload)


def test_split_config_accepts_proportions_that_sum_to_one() -> None:
    split = SplitConfig(train=0.7, val=0.15, test=0.15, seed=42)
    assert split.seed == 42


def test_split_config_rejects_proportions_that_dont_sum_to_one() -> None:
    with pytest.raises(ValidationError, match="sum"):
        SplitConfig(train=0.7, val=0.2, test=0.2, seed=42)


def test_load_quality_config_reads_the_real_file() -> None:
    # quality.yaml vive junto a pyproject.toml, en la raíz del paquete.
    config_path = Path(__file__).parent.parent / "quality.yaml"
    config = load_quality_config(config_path)

    assert config.checks["min_images_per_class"].threshold == 300
    assert config.checks["min_images_per_class"].severity == "fail"
    assert config.checks["min_images_per_class"].min_classes == 2
    assert set(config.checks.keys()) == REQUIRED_CHECKS


def test_check_config_accepts_min_classes() -> None:
    check = CheckConfig(threshold=300, severity="fail", min_classes=2)
    assert check.min_classes == 2


def test_check_config_rejects_min_classes_below_one() -> None:
    with pytest.raises(ValidationError, match="min_classes"):
        CheckConfig(threshold=300, severity="fail", min_classes=0)


def test_load_quality_config_raises_clear_error_when_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError, match="does_not_exist.yaml"):
        load_quality_config(missing_path)


def test_pipeline_settings_uses_default_dataset_version_when_env_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATASET_VERSION", raising=False)
    settings = PipelineSettings(_env_file=None)
    assert settings.dataset_version == "v0.0.0-dev"


def test_pipeline_settings_reads_dataset_version_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATASET_VERSION", "v2.3.0")
    settings = PipelineSettings(_env_file=None)
    assert settings.dataset_version == "v2.3.0"


def test_pipeline_settings_rejects_a_non_semantic_dataset_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATASET_VERSION", "latest")
    with pytest.raises(ValidationError, match="dataset_version"):
        PipelineSettings(_env_file=None)
