"""Photo enhancement module with safe transformations."""

import os
from pathlib import Path
from datetime import datetime, timedelta

from PIL import Image, ImageFilter, ImageStat

from app.config import get_settings
from app.models import PhotoEnhanceResult


MAX_DIMENSION = 2000
JPEG_QUALITY = 85
BACKGROUND_UNIFORMITY_THRESHOLD = 15  # Max std dev for "uniform" color


def _detect_uniform_background(image: Image.Image, border_size: int = 50) -> bool:
    """Check if image has uniform background on all borders."""
    width, height = image.size

    if width < border_size * 2 or height < border_size * 2:
        return False

    # Sample border regions
    regions = [
        image.crop((0, 0, width, border_size)),  # top
        image.crop((0, height - border_size, width, height)),  # bottom
        image.crop((0, 0, border_size, height)),  # left
        image.crop((width - border_size, 0, width, height)),  # right
    ]

    for region in regions:
        stat = ImageStat.Stat(region)
        # Check if all channels have low standard deviation
        if any(std > BACKGROUND_UNIFORMITY_THRESHOLD for std in stat.stddev):
            return False

    return True


def _find_content_bbox(image: Image.Image, border_size: int = 50) -> tuple[int, int, int, int] | None:
    """Find bounding box of non-background content."""
    width, height = image.size

    # Get average border color
    top = image.crop((0, 0, width, border_size))
    top_stat = ImageStat.Stat(top)
    bg_color = tuple(int(m) for m in top_stat.mean[:3])

    # Convert to grayscale difference from background
    gray = image.convert("RGB")
    pixels = gray.load()

    min_x, min_y = width, height
    max_x, max_y = 0, 0

    tolerance = 30

    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y][:3]
            diff = sum(abs(a - b) for a, b in zip(pixel, bg_color))
            if diff > tolerance * 3:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x <= min_x or max_y <= min_y:
        return None

    # Add padding
    padding = 20
    min_x = max(0, min_x - padding)
    min_y = max(0, min_y - padding)
    max_x = min(width, max_x + padding)
    max_y = min(height, max_y + padding)

    return (min_x, min_y, max_x, max_y)


def enhance_photo(input_path: str | Path, output_path: str | Path | None = None) -> PhotoEnhanceResult:
    """Enhance photo with safe transformations."""
    input_path = Path(input_path)

    if output_path is None:
        output_path = input_path.parent / f"enhanced_{input_path.name}"
    else:
        output_path = Path(output_path)

    with Image.open(input_path) as img:
        original_size = img.size
        was_cropped = False
        was_denoised = False

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Try auto-crop if uniform background detected
        if _detect_uniform_background(img):
            bbox = _find_content_bbox(img)
            if bbox:
                crop_width = bbox[2] - bbox[0]
                crop_height = bbox[3] - bbox[1]
                # Only crop if it removes significant border
                if crop_width < original_size[0] * 0.9 or crop_height < original_size[1] * 0.9:
                    img = img.crop(bbox)
                    was_cropped = True

        # Apply mild denoise
        img = img.filter(ImageFilter.MedianFilter(size=3))
        was_denoised = True

        # Resize if too large
        width, height = img.size
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
            new_size = (int(width * ratio), int(height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        final_size = img.size

        # Save with optimization
        img.save(
            output_path,
            "JPEG",
            quality=JPEG_QUALITY,
            optimize=True,
        )

    return PhotoEnhanceResult(
        path=str(output_path),
        original_size=original_size,
        final_size=final_size,
        was_cropped=was_cropped,
        was_denoised=was_denoised,
    )


def cleanup_tmp_files(max_age_hours: int = 24) -> int:
    """Remove old temporary files. Returns count of deleted files."""
    settings = get_settings()
    tmp_dir = Path(settings.tmp_dir)

    if not tmp_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    deleted = 0

    for file_path in tmp_dir.iterdir():
        if file_path.name == ".keep":
            continue

        if file_path.is_file():
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff:
                try:
                    file_path.unlink()
                    deleted += 1
                except OSError:
                    pass

    return deleted


def format_enhance_report(result: PhotoEnhanceResult) -> str:
    """Format enhancement result as user-friendly message."""
    lines = ["✨ **Фото улучшено**"]

    if result.was_cropped:
        lines.append("✂️ Обрезан фон")

    if result.was_denoised:
        lines.append("🔇 Уменьшен шум")

    if result.original_size != result.final_size:
        lines.append(
            f"📐 Размер: {result.original_size[0]}×{result.original_size[1]} → "
            f"{result.final_size[0]}×{result.final_size[1]}"
        )

    return "\n".join(lines)
