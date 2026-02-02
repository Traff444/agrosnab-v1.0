"""Photo quality analysis module."""

from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from app.config import get_settings
from app.models import PhotoQualityResult, PhotoStatus

PREVIEW_SIZE = 512


def _calculate_sharpness(image: Image.Image) -> float:
    """Calculate sharpness using edge variance method."""
    # Convert to grayscale for edge detection
    gray = image.convert("L")

    # Apply edge detection filter
    edges = gray.filter(ImageFilter.FIND_EDGES)

    # Calculate variance of edge intensities
    stat = ImageStat.Stat(edges)
    return stat.var[0]


def _calculate_brightness_percentiles(image: Image.Image) -> tuple[float, float]:
    """Calculate 10th and 90th percentile brightness."""
    gray = image.convert("L")
    histogram = gray.histogram()

    total_pixels = sum(histogram)
    cumsum = 0
    p10 = 0
    p90 = 255

    # Find 10th percentile
    target_10 = total_pixels * 0.1
    for i, count in enumerate(histogram):
        cumsum += count
        if cumsum >= target_10 and p10 == 0:
            p10 = i
        if cumsum >= total_pixels * 0.9:
            p90 = i
            break

    return float(p10), float(p90)


def analyze_photo(file_path: str | Path) -> PhotoQualityResult:
    """Analyze photo quality and return assessment."""
    settings = get_settings()
    file_path = Path(file_path)

    with Image.open(file_path) as img:
        original_width, original_height = img.size

        # Create preview for consistent analysis
        preview = img.copy()
        preview.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)

        sharpness = _calculate_sharpness(preview)
        brightness_low, brightness_high = _calculate_brightness_percentiles(preview)

    warnings = []
    status = PhotoStatus.OK

    # Check dimensions
    min_dimension = min(original_width, original_height)
    if min_dimension < settings.photo_min_size:
        warnings.append(
            f"Размер {min_dimension}px меньше рекомендуемого {settings.photo_min_size}px"
        )
        status = PhotoStatus.WARNING

    # Check sharpness
    if sharpness < settings.photo_sharpness_threshold:
        warnings.append(
            f"Низкая резкость ({sharpness:.0f} < {settings.photo_sharpness_threshold:.0f})"
        )
        status = PhotoStatus.WARNING

    # Check brightness
    if brightness_low < settings.photo_brightness_min:
        warnings.append(f"Темные области слишком тёмные ({brightness_low:.0f})")
        status = PhotoStatus.WARNING

    if brightness_high > settings.photo_brightness_max:
        warnings.append(f"Светлые области слишком яркие ({brightness_high:.0f})")
        status = PhotoStatus.WARNING

    return PhotoQualityResult(
        status=status,
        width=original_width,
        height=original_height,
        sharpness=sharpness,
        brightness_low=brightness_low,
        brightness_high=brightness_high,
        warnings=warnings,
    )


def format_quality_report(result: PhotoQualityResult) -> str:
    """Format quality result as user-friendly message."""
    emoji = "✅" if result.status == PhotoStatus.OK else "⚠️"

    lines = [
        f"{emoji} **Качество фото**",
        f"📐 Размер: {result.width}×{result.height}px",
        f"🔍 Резкость: {result.sharpness:.0f}",
        f"☀️ Яркость: {result.brightness_low:.0f}-{result.brightness_high:.0f}",
    ]

    if result.warnings:
        lines.append("")
        lines.append("⚠️ **Замечания:**")
        for warning in result.warnings:
            lines.append(f"  • {warning}")

    return "\n".join(lines)
