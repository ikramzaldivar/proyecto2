"""Genera el dataset sintético de la demo: imágenes JPEG y su COCO.

Esto es ORQUESTACION, no logica de calidad: llama a
`dataset_quality.demo.synthetic` y escribe el resultado en disco.

    PYTHONPATH=quality/src python pipeline/make_demo_dataset.py --out demo

Escribe `demo/images/*.jpg` y `demo/coco.json`. La carpeta `demo/` esta en
`.gitignore`: el proyecto no versiona imagenes en git, se regeneran con la
misma semilla.
"""

import argparse
import json
from pathlib import Path

from dataset_quality.demo.synthetic import build_demo_dataset, render_demo_image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=Path("demo"), help="Carpeta de salida")
    parser.add_argument("--images", type=int, default=40, help="Numero de imagenes")
    parser.add_argument("--seed", type=int, default=7, help="Semilla (mismo valor, mismo dataset)")
    args = parser.parse_args()

    dataset = build_demo_dataset(seed=args.seed, image_count=args.images)

    images_dir = args.out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for spec in dataset.images:
        render_demo_image(spec).save(images_dir / spec.file_name, quality=spec.jpeg_quality)

    (args.out / "coco.json").write_text(json.dumps(dataset.coco, indent=2) + "\n", encoding="utf-8")

    planted = [spec for spec in dataset.images if spec.duplicate_of is not None]
    print(
        f"{len(dataset.images)} imagenes y {len(dataset.coco['annotations'])} cajas en {args.out} "
        f"(seed {args.seed}; par de duplicados plantado: "
        f"{planted[0].file_name} <- {planted[0].duplicate_of})"
    )


if __name__ == "__main__":
    main()
