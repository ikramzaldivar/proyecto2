import pytest
from pydantic import ValidationError

from dataset_quality.policy.version_registry import (
    VersionsFile,
    build_version_entry,
    register_version,
)

MINIMUM_IMAGES_PER_CLASS = 300


def _release(*, images: int = 689) -> dict:
    """Recorte de un release.json real: solo los campos que consume el registro."""
    return {
        "generated_at": "2026-09-18T19:58:20.988152Z",
        "totals": {"images": images, "annotations": 1455, "categories": 3},
        "analyzers": {
            "small_objects": {"small_percent": 0.4123711340206186},
            "class_imbalance": {"ratio": 5.929577464788732},
            "duplicates": {"duplicate_groups": [[10, 11], [20, 21, 22]]},
            "invalid_boxes": {"invalid_count": 2},
        },
        "class_counts": [
            {"category_id": 1, "distinct_images_before": 421, "distinct_images_after": 421},
            {"category_id": 2, "distinct_images_before": 400, "distinct_images_after": 399},
            {"category_id": 3, "distinct_images_before": 71, "distinct_images_after": 71},
        ],
    }


def _entry(version: str = "v1.0.0", **overrides):
    kwargs = {
        "version": version,
        "commit": "abc1234",
        "dvc_revision": "2ae957bda56b5cf9293fd620b781e699",
        "parent_version": None,
    }
    kwargs.update(overrides)
    return build_version_entry(_release(), **kwargs)


def test_entry_copies_totals_and_metrics_from_the_release() -> None:
    entry = _entry()

    assert entry.version == "v1.0.0"
    assert entry.created_at == "2026-09-18T19:58:20.988152Z"
    assert entry.totals.images == 689
    assert entry.totals.annotations == 1455
    assert entry.metrics.small_objects_percent == pytest.approx(0.4123711340206186)
    assert entry.metrics.class_imbalance_ratio == pytest.approx(5.929577464788732)
    assert entry.metrics.duplicate_groups == 2
    assert entry.metrics.invalid_boxes == 2


def test_class_counts_use_the_count_after_collapsing_duplicates() -> None:
    # Es la cifra que decide M3: la clase 2 baja de 400 a 399 al colapsar copias.
    entry = _entry()

    by_category = {item.category_id: item.distinct_images for item in entry.class_counts}
    assert by_category == {1: 421, 2: 399, 3: 71}


def test_environments_are_not_pushed_unless_a_hash_is_given() -> None:
    entry = _entry()

    assert entry.environments.dev.status == "not_pushed"
    assert entry.environments.dev.content_hash is None
    assert entry.environments.prod.status == "not_pushed"


def test_a_hash_marks_that_environment_as_pushed() -> None:
    entry = _entry(dev_content_hash="2ae957bd", prod_content_hash="2ae957bd")

    assert entry.environments.dev.status == "pushed"
    assert entry.environments.dev.content_hash == "2ae957bd"
    assert entry.environments.prod.status == "pushed"
    assert entry.environments.prod.content_hash == "2ae957bd"


@pytest.mark.parametrize("bad_version", ["1.0.0", "v1.0", "v1.0.0-dev", "latest", ""])
def test_version_must_be_semantic_and_the_error_names_the_field(bad_version: str) -> None:
    with pytest.raises(ValidationError) as error:
        _entry(version=bad_version)

    assert error.value.errors()[0]["loc"] == ("version",)


def test_a_release_missing_a_field_is_rejected_naming_it() -> None:
    release = _release()
    del release["analyzers"]["invalid_boxes"]

    with pytest.raises(ValidationError) as error:
        build_version_entry(
            release, version="v1.0.0", commit=None, dvc_revision=None, parent_version=None
        )

    assert "invalid_boxes" in str(error.value)


def test_register_appends_and_links_each_version_to_its_parent() -> None:
    registry = register_version(None, _entry("v1.0.0"), MINIMUM_IMAGES_PER_CLASS)
    registry = register_version(registry, _entry("v1.1.0"), MINIMUM_IMAGES_PER_CLASS)

    assert [v.version for v in registry.versions] == ["v1.0.0", "v1.1.0"]
    assert registry.versions[0].parent_version is None
    assert registry.versions[1].parent_version == "v1.0.0"
    assert registry.minimum_images_per_class == MINIMUM_IMAGES_PER_CLASS


def test_registering_the_same_version_again_replaces_it_instead_of_duplicating() -> None:
    registry = register_version(None, _entry("v1.0.0"), MINIMUM_IMAGES_PER_CLASS)
    registry = register_version(
        registry, _entry("v1.0.0", commit="def5678"), MINIMUM_IMAGES_PER_CLASS
    )

    assert [v.version for v in registry.versions] == ["v1.0.0"]
    assert registry.versions[0].commit == "def5678"
    assert registry.versions[0].parent_version is None


def test_dump_uses_the_camel_case_keys_the_portal_contract_expects() -> None:
    registry = register_version(None, _entry("v1.0.0"), MINIMUM_IMAGES_PER_CLASS)

    dumped = registry.model_dump(mode="json", by_alias=True)

    assert set(dumped) == {"minimumImagesPerClass", "versions"}
    assert set(dumped["versions"][0]) == {
        "version",
        "createdAt",
        "commit",
        "dvcRevision",
        "parentVersion",
        "environments",
        "totals",
        "metrics",
        "classCounts",
    }
    assert set(dumped["versions"][0]["metrics"]) == {
        "smallObjectsPercent",
        "classImbalanceRatio",
        "duplicateGroups",
        "invalidBoxes",
    }
    assert dumped["versions"][0]["classCounts"][0] == {"categoryId": 1, "distinctImages": 421}
    assert dumped["versions"][0]["environments"]["dev"] == {
        "status": "not_pushed",
        "contentHash": None,
    }


def test_registry_can_be_reloaded_from_its_own_dump() -> None:
    registry = register_version(None, _entry("v1.0.0"), MINIMUM_IMAGES_PER_CLASS)
    dumped = registry.model_dump(mode="json", by_alias=True)

    reloaded = VersionsFile.model_validate(dumped)

    assert reloaded == registry
