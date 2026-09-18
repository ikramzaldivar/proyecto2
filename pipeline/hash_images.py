"""Etapa 1 del pipeline: calcula el pHash de cada imagen del dataset.

Esto es ORQUESTACION, no logica de calidad: no decide nada sobre el dataset,
solo recorre las imagenes versionadas con DVC y llama al adaptador
`dataset_quality.adapters.phash`. Vive en una etapa aparte porque es la unica
parte que toca el sistema de archivos imagen por imagen (cara), y asi DVC la
cachea y no la vuelve a correr cuando lo unico que cambia son los umbrales de
`quality.yaml`.

La salida se ordena siempre igual (sort_keys) para que dos corridas sobre el
mismo dataset den el mismo archivo byte por byte y DVC pueda cachearla.
"""

import argparse
import json
from pathlib import Path

from dataset_quality.adapters.phash import compute_phash

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, type=Path, help="Carpeta con las imagenes")
    parser.add_argument("--out", required=True, type=Path, help="JSON de salida con los hashes")
    args = parser.parse_args()

    if not args.images.is_dir():
        raise SystemExit(f"no existe la carpeta de imagenes: {args.images}")

    hashes: dict[str, str] = {}
    failed: list[dict[str, str]] = []

    files = sorted(
        path
        for path in args.images.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    )

    for path in files:
        key = path.relative_to(args.images).as_posix()
        try:
            hashes[key] = compute_phash(path)
        except Exception as error:  # noqa: BLE001 - un archivo corrupto no debe tumbar la etapa
            failed.append({"file": key, "error": f"{type(error).__name__}: {error}"})

    payload = {
        "images_dir": args.images.as_posix(),
        "hashed_count": len(hashes),
        "failed": failed,
        "hashes": hashes,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"pHash calculado para {len(hashes)} imagenes ({len(failed)} fallidas) -> {args.out}")


if __name__ == "__main__":
    main()
