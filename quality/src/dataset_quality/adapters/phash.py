from pathlib import Path

import imagehash
from PIL import Image


def compute_phash(image_path: Path) -> str:
    """Lee un archivo de imagen y calcula su hash perceptual (pHash).

    A diferencia de un hash criptográfico (MD5/SHA), el pHash compara
    CONTENIDO VISUAL: dos imágenes casi idénticas (una reescalada, una
    recomprimida) producen hashes muy cercanos entre sí, aunque sus bytes
    sean completamente distintos. Esto toca el sistema de archivos, por
    eso vive en la capa adapters (CAL 00) y no en analyzers/.
    """
    with Image.open(image_path) as image:
        return str(imagehash.phash(image))
