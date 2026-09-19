"""Dataset COCO sintético para la demo (`make demo`).

Sirve para ver las seis pantallas con cifras cuando no hay acceso a los
remotos de DVC. Las imágenes NO se versionan: se generan al vuelo a partir de
una semilla, así que no hay binarios en git y el resultado es reproducible.

Funciones puras (CAL 00): `build_demo_dataset` solo devuelve especificaciones y
el COCO; `render_demo_image` dibuja una imagen en memoria. Escribir a disco es
trabajo de `pipeline/make_demo_dataset.py`.

El dataset está armado a propósito para que cada analizador tenga algo que
mostrar sin bloquear la compuerta de la demo: tres clases desbalanceadas, dos
objetos pequeños, cero cajas inválidas y UN par de casi-duplicados (una copia
recomprimida de otra imagen), que llega como `warn`.
"""

import random
from dataclasses import dataclass

from PIL import Image, ImageDraw

IMAGE_WIDTH = 320
IMAGE_HEIGHT = 240

CATEGORIES = ({"id": 1, "name": "person"}, {"id": 2, "name": "car"}, {"id": 3, "name": "dog"})

# Reparto de la clase principal de cada imagen: person > car > dog, como en el
# dataset real, para que el desbalance del reporte sea plausible.
_CLASS_SHARES = ((1, 0.55), (2, 0.30), (3, 0.15))

_CLASS_COLORS = {1: (220, 60, 60), 2: (60, 90, 220), 3: (60, 180, 90)}

# Índices de imágenes únicas que reciben un objeto pequeño (< 32 x 32 px).
_SMALL_OBJECT_IMAGES = (3, 17)

# Imagen que se copia y recomprime para plantar el par de casi-duplicados.
_DUPLICATED_IMAGE = 5
_DUPLICATE_JPEG_QUALITY = 35
_DEFAULT_JPEG_QUALITY = 90


@dataclass(frozen=True)
class DemoBox:
    category_id: int
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class DemoImage:
    file_name: str
    width: int
    height: int
    background_seed: int
    boxes: tuple[DemoBox, ...]
    jpeg_quality: int = _DEFAULT_JPEG_QUALITY
    duplicate_of: str | None = None


@dataclass(frozen=True)
class DemoDataset:
    coco: dict
    images: tuple[DemoImage, ...]


def _primary_classes(count: int, rng: random.Random) -> list[int]:
    """Una clase principal por imagen, respetando el reparto y mezclada."""
    classes: list[int] = []
    for category_id, share in _CLASS_SHARES:
        classes.extend([category_id] * round(count * share))
    while len(classes) < count:
        classes.append(_CLASS_SHARES[0][0])
    classes = classes[:count]
    rng.shuffle(classes)
    return classes


def _random_box(category_id: int, rng: random.Random) -> DemoBox:
    width = rng.randint(48, 140)
    height = rng.randint(48, 110)
    return DemoBox(
        category_id=category_id,
        x=rng.randint(0, IMAGE_WIDTH - width),
        y=rng.randint(0, IMAGE_HEIGHT - height),
        width=width,
        height=height,
    )


def _build_image(index: int, primary: int, rng: random.Random) -> DemoImage:
    boxes = [_random_box(primary, rng)]
    if rng.random() < 0.4:
        boxes.append(_random_box(primary, rng))
    if index in _SMALL_OBJECT_IMAGES:
        boxes.append(
            DemoBox(
                category_id=1,
                x=rng.randint(0, IMAGE_WIDTH - 20),
                y=rng.randint(0, IMAGE_HEIGHT - 22),
                width=20,
                height=22,
            )
        )
    return DemoImage(
        file_name=f"demo_{index:03d}.jpg",
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        background_seed=rng.randrange(2**31),
        boxes=tuple(boxes),
    )


def build_demo_dataset(seed: int = 7, image_count: int = 40) -> DemoDataset:
    """Especificación determinista del dataset: mismo `seed`, mismo resultado."""
    rng = random.Random(seed)
    unique_count = image_count - 1
    primaries = _primary_classes(unique_count, rng)
    images = [_build_image(index, primaries[index], rng) for index in range(unique_count)]

    original = images[_DUPLICATED_IMAGE]
    images.append(
        DemoImage(
            file_name=f"demo_{unique_count:03d}_copia.jpg",
            width=original.width,
            height=original.height,
            background_seed=original.background_seed,
            boxes=original.boxes,
            jpeg_quality=_DUPLICATE_JPEG_QUALITY,
            duplicate_of=original.file_name,
        )
    )

    coco_images = []
    coco_annotations = []
    for image_id, image in enumerate(images, start=1):
        coco_images.append(
            {
                "id": image_id,
                "file_name": image.file_name,
                "width": image.width,
                "height": image.height,
            }
        )
        for box in image.boxes:
            coco_annotations.append(
                {
                    "id": len(coco_annotations) + 1,
                    "image_id": image_id,
                    "category_id": box.category_id,
                    "bbox": [box.x, box.y, box.width, box.height],
                    "area": box.width * box.height,
                    "iscrowd": 0,
                }
            )

    coco = {
        "images": coco_images,
        "categories": [dict(category) for category in CATEGORIES],
        "annotations": coco_annotations,
    }
    return DemoDataset(coco=coco, images=tuple(images))


def render_demo_image(spec: DemoImage) -> Image.Image:
    """Dibuja la imagen en memoria: fondo de bloques aleatorios y una caja por objeto.

    El fondo depende solo de `background_seed`, así que dos imágenes distintas
    tienen pHash muy lejano y la copia (misma semilla) queda a distancia mínima.
    """
    rng = random.Random(spec.background_seed)
    columns, rows = 8, 6
    blocks = Image.new("RGB", (columns, rows))
    for column in range(columns):
        for row in range(rows):
            shade = rng.randint(50, 210)
            blocks.putpixel((column, row), (shade, rng.randint(50, 210), shade))
    image = blocks.resize((spec.width, spec.height), Image.NEAREST)

    draw = ImageDraw.Draw(image)
    for box in spec.boxes:
        draw.rectangle(
            [box.x, box.y, box.x + box.width - 1, box.y + box.height - 1],
            fill=_CLASS_COLORS[box.category_id],
            outline=(255, 255, 255),
        )
    return image
