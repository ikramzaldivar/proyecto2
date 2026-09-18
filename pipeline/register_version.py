"""Registra un release en `versions.json` (el historial que lee la vista Versions).

Esto es ORQUESTACION, no logica de calidad: lee `release.json`, llama a las
funciones puras de `dataset_quality.policy.version_registry` y escribe el
registro. Corre DESPUES de la etapa `release`, a mano y solo cuando el equipo
decide cortar una version:

    PYTHONPATH=quality/src python pipeline/register_version.py \\
        --release reports/release.json --config quality/quality.yaml \\
        --registry reports/versions.json --version v1.0.0

`PYTHONPATH=quality/src` es el mismo atajo que usan las etapas de `dvc.yaml`:
evita instalar el paquete solo para correr el script.

`reports/versions.json` SI se versiona en git (a diferencia del resto de
`reports/`): es el historial de releases y no se puede regenerar desde cero.

Un release cuya compuerta quedo en `fail` NO se registra: "un fail bloquea el
release" tambien significa que no recibe version.

Los hashes por entorno (`--dev-hash`, `--prod-hash`) se pasan solo cuando el
`dvc push` a ese remoto ya ocurrio; sin ellos la version queda `not_pushed`.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from dataset_quality.adapters.config_loader import load_quality_config
from dataset_quality.policy.version_registry import (
    VersionsFile,
    build_version_entry,
    register_version,
)

RAW_DVC_FILE = Path("data/raw.dvc")


def current_commit() -> str | None:
    """Hash corto del commit de git, o None si no hay git o no es un repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def dataset_content_hash() -> str | None:
    """Hash de contenido del dataset segun `data/raw.dvc` (sin el sufijo `.dir`)."""
    if not RAW_DVC_FILE.exists():
        return None
    document = yaml.safe_load(RAW_DVC_FILE.read_text(encoding="utf-8")) or {}
    outs = document.get("outs") or []
    if not outs or "md5" not in outs[0]:
        return None
    return str(outs[0]["md5"]).removesuffix(".dir")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--release", required=True, type=Path, help="release.json de la etapa release"
    )
    parser.add_argument("--config", required=True, type=Path, help="quality.yaml")
    parser.add_argument("--registry", required=True, type=Path, help="versions.json a actualizar")
    parser.add_argument("--version", required=True, help="Version semantica: v1.2.0")
    parser.add_argument("--commit", default=None, help="Por defecto, git rev-parse --short HEAD")
    parser.add_argument("--dvc-revision", default=None, help="Por defecto, el md5 de data/raw.dvc")
    parser.add_argument("--dev-hash", default=None, help="Hash del dataset ya empujado a DEV")
    parser.add_argument("--prod-hash", default=None, help="Hash del dataset ya empujado a PROD")
    args = parser.parse_args()

    release = json.loads(args.release.read_text(encoding="utf-8"))

    status = release.get("quality", {}).get("overall_status")
    if status != "pass":
        print(
            f"Error: la compuerta de calidad quedo en '{status}' en {args.release}. "
            "Un release bloqueado no se registra como version: corrige los checks en fail "
            "y vuelve a correr `dvc repro`.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    config = load_quality_config(args.config)
    minimum = int(config.checks["min_images_per_class"].threshold)

    registry = (
        VersionsFile.model_validate_json(args.registry.read_text(encoding="utf-8"))
        if args.registry.exists()
        else None
    )

    try:
        entry = build_version_entry(
            release,
            version=args.version,
            commit=args.commit or current_commit(),
            dvc_revision=args.dvc_revision or dataset_content_hash(),
            parent_version=None,
            dev_content_hash=args.dev_hash,
            prod_content_hash=args.prod_hash,
        )
    except ValidationError as error:
        for problem in error.errors():
            if problem["loc"] == ("version",):
                print(
                    f"Error: '{args.version}' no es una versión semántica. "
                    "Usa el formato vMAYOR.MENOR.PARCHE, por ejemplo v1.2.0.",
                    file=sys.stderr,
                )
                raise SystemExit(1) from error
        print(f"Error: release.json no cumple lo que espera el registro:\n{error}", file=sys.stderr)
        raise SystemExit(1) from error

    updated = register_version(registry, entry, minimum)

    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(
        json.dumps(updated.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )

    registered = (
        updated.versions[-1]
        if registry is None
        else next(v for v in updated.versions if v.version == args.version)
    )
    print(
        f"version {registered.version} registrada en {args.registry} "
        f"({len(updated.versions)} en total; padre: {registered.parent_version or 'ninguno'})"
    )


if __name__ == "__main__":
    main()
