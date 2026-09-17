import pytest
from pydantic import ValidationError

from dataset_quality.models.config import CheckConfig, PipelineSettings, QualityConfig, SplitConfig


def test_check_config_accepts_valid_severity() -> None:
    check = CheckConfig(threshold=300, severity="fail")
    assert check.severity == "fail"


def test_check_config_rejects_invalid_severity() -> None:
    # CAL 02: "severidad inválida" — solo "warn" o "fail" son válidos.
    with pytest.raises(ValidationError, match="severity"):
        CheckConfig(threshold=300, severity="critical")


def test_quality_config_rejects_missing_severity() -> None:
    # CAL 02: "configuraciones faltantes" — threshold sin severity.
    with pytest.raises(ValidationError, match="severity"):
        QualityConfig.model_validate({"checks": {"min_images_per_class": {"threshold": 300}}})


def test_split_config_accepts_proportions_that_sum_to_one() -> None:
    split = SplitConfig(train=0.7, val=0.15, test=0.15, seed=42)
    assert split.seed == 42


def test_split_config_rejects_proportions_that_dont_sum_to_one() -> None:
    # CAL 02: "proporciones que no suman uno".
    with pytest.raises(ValidationError, match="sum"):
        SplitConfig(train=0.7, val=0.2, test=0.2, seed=42)


def test_pipeline_settings_requires_coco_source_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATASET_QUALITY_COCO_SOURCE_PATH", raising=False)
    with pytest.raises(ValidationError, match="coco_source_path"):
        PipelineSettings()


def test_pipeline_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATASET_QUALITY_COCO_SOURCE_PATH", "/data/dataset.json")
    settings = PipelineSettings()
    assert settings.coco_source_path == "/data/dataset.json"
