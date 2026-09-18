from pathlib import Path

from PIL import Image, ImageDraw

from dataset_quality.adapters.phash import compute_phash
from dataset_quality.analyzers.duplicates import analyze_duplicates
from dataset_quality.models.config import CheckConfig


def _make_base_image() -> Image.Image:
    image = Image.new("RGB", (200, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, 100, 100], fill=(255, 0, 0))
    draw.ellipse([100, 100, 180, 180], fill=(0, 0, 255))
    return image


def _make_different_image() -> Image.Image:
    image = Image.new("RGB", (200, 200), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(10, 190), (190, 190), (100, 10)], fill=(0, 255, 0))
    return image


def test_detects_exact_copy_rescaled_and_recompressed_as_duplicates(tmp_path: Path) -> None:
    # CAL 05, criterio de cierre: "las tres variantes aparecen en el
    # reporte" — copia exacta, reescalada, recomprimida.
    base = _make_base_image()

    exact_path = tmp_path / "exact.png"
    base.save(exact_path)

    rescaled_path = tmp_path / "rescaled.png"
    base.resize((80, 80)).save(rescaled_path)

    recompressed_path = tmp_path / "recompressed.jpg"
    base.save(recompressed_path, "JPEG", quality=30)

    different_path = tmp_path / "different.png"
    _make_different_image().save(different_path)

    hashes = {
        1: compute_phash(exact_path),
        2: compute_phash(rescaled_path),
        3: compute_phash(recompressed_path),
        4: compute_phash(different_path),
    }

    report = analyze_duplicates(hashes, CheckConfig(threshold=8, severity="warn"))

    # Las 3 variantes de la MISMA imagen deben quedar en el mismo grupo.
    duplicate_group = next(group for group in report.duplicate_groups if 1 in group)
    assert set(duplicate_group) == {1, 2, 3}

    # La imagen genuinamente distinta no debe aparecer en ese grupo.
    assert 4 not in duplicate_group


def test_phash_is_stable_across_file_format_changes(tmp_path: Path) -> None:
    # CAL 05: "el algoritmo no depende únicamente de MD5 o SHA" — un hash
    # criptográfico cambiaría por completo ante cualquier cambio de bytes
    # (como guardar el mismo pixel data en JPEG en vez de PNG). pHash debe
    # seguir siendo el mismo (o casi) porque compara contenido visual, no bytes.
    base = _make_base_image()

    png_path = tmp_path / "base.png"
    base.save(png_path)

    jpeg_path = tmp_path / "base.jpg"
    base.save(jpeg_path, "JPEG", quality=95)

    png_hash = compute_phash(png_path)
    jpeg_hash = compute_phash(jpeg_path)

    # No exigimos que sean IDÉNTICOS (JPEG con pérdida sí cambia algo), pero
    # si compute_phash fuera en realidad un hash de bytes (MD5/SHA), la
    # distancia sería enorme (básicamente aleatoria) — con pHash real debe
    # quedar muy cerca de 0.
    report = analyze_duplicates(
        {1: png_hash, 2: jpeg_hash}, CheckConfig(threshold=8, severity="warn")
    )
    assert len(report.pairs) == 1
