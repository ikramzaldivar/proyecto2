"""Registro de versiones del dataset (`versions.json`).

Funciones puras (CAL 00): reciben el `release.json` ya cargado y devuelven
modelos Pydantic. No leen disco, no llaman a git ni a DVC: el commit, la
revisión de DVC y los hashes por entorno llegan como argumentos desde
`pipeline/register_version.py`.

El formato de salida es el `versionsFileSchema` de
`backend/src/logic/quality/contracts.ts`, que el portal valida con Zod:
llaves en camelCase y `minimumImagesPerClass` en la raíz. Por eso los
modelos usan alias y se vuelcan con `by_alias=True`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Versión semántica con prefijo "v": v1.2.0. Sin sufijos (v1.0.0-dev no es un
# release, es el valor por defecto de build_release.py cuando no se fijó uno).
SEMANTIC_VERSION_PATTERN = r"^v\d+\.\d+\.\d+$"


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class _ReleaseTotals(BaseModel):
    images: int
    annotations: int
    categories: int


class _SmallObjects(BaseModel):
    small_percent: float


class _ClassImbalance(BaseModel):
    ratio: float


class _Duplicates(BaseModel):
    duplicate_groups: list[list[int]]


class _InvalidBoxes(BaseModel):
    invalid_count: int


class _ReleaseAnalyzers(BaseModel):
    small_objects: _SmallObjects
    class_imbalance: _ClassImbalance
    duplicates: _Duplicates
    invalid_boxes: _InvalidBoxes


class _ReleaseClassCount(BaseModel):
    category_id: int
    distinct_images_after: int


class ReleaseSummary(BaseModel):
    """Los campos de `release.json` que el registro necesita; el resto se ignora."""

    generated_at: str
    totals: _ReleaseTotals
    analyzers: _ReleaseAnalyzers
    class_counts: list[_ReleaseClassCount]


class VersionEnvironment(_Camel):
    status: Literal["pushed", "not_pushed"]
    content_hash: str | None


class VersionEnvironments(_Camel):
    dev: VersionEnvironment
    prod: VersionEnvironment


class VersionMetrics(_Camel):
    small_objects_percent: float
    class_imbalance_ratio: float
    duplicate_groups: int
    invalid_boxes: int


class VersionClassCount(_Camel):
    category_id: int
    distinct_images: int


class VersionEntry(_Camel):
    version: str = Field(pattern=SEMANTIC_VERSION_PATTERN)
    created_at: str
    commit: str | None
    dvc_revision: str | None
    parent_version: str | None
    environments: VersionEnvironments
    totals: _ReleaseTotals
    metrics: VersionMetrics
    class_counts: list[VersionClassCount]


class VersionsFile(_Camel):
    minimum_images_per_class: int
    versions: list[VersionEntry]


def _environment(content_hash: str | None) -> VersionEnvironment:
    if content_hash is None:
        return VersionEnvironment(status="not_pushed", content_hash=None)
    return VersionEnvironment(status="pushed", content_hash=content_hash)


def build_version_entry(
    release: dict,
    *,
    version: str,
    commit: str | None,
    dvc_revision: str | None,
    parent_version: str | None,
    dev_content_hash: str | None = None,
    prod_content_hash: str | None = None,
) -> VersionEntry:
    """Resume un `release.json` en una entrada del registro.

    `class_counts` toma el conteo DESPUÉS de colapsar duplicados
    (`distinct_images_after`): es el que decide si una clase llega al mínimo
    del curso, y el que la vista Versions compara entre releases.
    """
    summary = ReleaseSummary.model_validate(release)

    return VersionEntry(
        version=version,
        created_at=summary.generated_at,
        commit=commit,
        dvc_revision=dvc_revision,
        parent_version=parent_version,
        environments=VersionEnvironments(
            dev=_environment(dev_content_hash), prod=_environment(prod_content_hash)
        ),
        totals=summary.totals,
        metrics=VersionMetrics(
            small_objects_percent=summary.analyzers.small_objects.small_percent,
            class_imbalance_ratio=summary.analyzers.class_imbalance.ratio,
            duplicate_groups=len(summary.analyzers.duplicates.duplicate_groups),
            invalid_boxes=summary.analyzers.invalid_boxes.invalid_count,
        ),
        class_counts=[
            VersionClassCount(
                category_id=item.category_id, distinct_images=item.distinct_images_after
            )
            for item in summary.class_counts
        ],
    )


def register_version(
    registry: VersionsFile | None, entry: VersionEntry, minimum_images_per_class: int
) -> VersionsFile:
    """Agrega `entry` al registro y devuelve uno nuevo (no muta el original).

    Una versión nueva queda encadenada a la anterior (`parent_version`).
    Registrar de nuevo una versión que ya existe la REEMPLAZA en su lugar y
    conserva su padre: re-cortar v1.0.0 no debe duplicarla ni reordenarla.
    """
    existing = list(registry.versions) if registry is not None else []

    for index, current in enumerate(existing):
        if current.version == entry.version:
            replaced = entry.model_copy(update={"parent_version": current.parent_version})
            existing[index] = replaced
            return VersionsFile(
                minimum_images_per_class=minimum_images_per_class, versions=existing
            )

    parent = existing[-1].version if existing else None
    linked = entry.model_copy(update={"parent_version": parent})
    return VersionsFile(
        minimum_images_per_class=minimum_images_per_class, versions=[*existing, linked]
    )
