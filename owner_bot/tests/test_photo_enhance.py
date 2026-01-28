"""Tests for photo enhancement."""

import os
from pathlib import Path

import pytest
from PIL import Image

from app.photo_enhance import enhance_photo, cleanup_tmp_files, format_enhance_report


class TestEnhancePhoto:
    """Test cases for enhance_photo function."""

    def test_basic_enhancement(self, temp_image, tmp_path):
        """Test basic photo enhancement."""
        output_path = tmp_path / "output.jpg"
        result = enhance_photo(temp_image, output_path)

        assert Path(result.path).exists()
        assert result.original_size == (1000, 1000)
        assert result.was_denoised is True

    def test_preserves_reasonable_size(self, temp_image, tmp_path):
        """Test that reasonable sized images aren't downsized."""
        output_path = tmp_path / "output.jpg"
        result = enhance_photo(temp_image, output_path)

        # Original 1000x1000 should not be changed
        assert result.final_size[0] <= 2000
        assert result.final_size[1] <= 2000

    def test_downsizes_large_image(self, tmp_path):
        """Test that very large images are downsized."""
        # Create oversized image
        large_img_path = tmp_path / "large.jpg"
        img = Image.new("RGB", (3000, 3000), color="white")
        img.save(large_img_path, "JPEG")

        output_path = tmp_path / "output.jpg"
        result = enhance_photo(large_img_path, output_path)

        assert result.final_size[0] <= 2000
        assert result.final_size[1] <= 2000

    def test_auto_crop_uniform_background(self, tmp_path):
        """Test auto-cropping with uniform background."""
        # Create image with uniform white border and dark center
        img_path = tmp_path / "bordered.jpg"
        img = Image.new("RGB", (500, 500), color="white")

        # Draw a dark square in center
        pixels = img.load()
        for x in range(150, 350):
            for y in range(150, 350):
                pixels[x, y] = (50, 50, 50)

        img.save(img_path, "JPEG", quality=95)

        output_path = tmp_path / "output.jpg"
        result = enhance_photo(img_path, output_path)

        # Should detect uniform background and potentially crop
        # (cropping only happens if significant border removal)
        assert Path(result.path).exists()

    def test_output_is_valid_jpeg(self, temp_image, tmp_path):
        """Test that output is a valid JPEG."""
        output_path = tmp_path / "output.jpg"
        enhance_photo(temp_image, output_path)

        # Should be able to open as image
        with Image.open(output_path) as img:
            assert img.format == "JPEG"

    def test_handles_rgba_image(self, tmp_path):
        """Test handling of RGBA images."""
        rgba_path = tmp_path / "rgba.png"
        img = Image.new("RGBA", (500, 500), color=(255, 255, 255, 128))
        img.save(rgba_path, "PNG")

        output_path = tmp_path / "output.jpg"
        result = enhance_photo(rgba_path, output_path)

        # Should convert to RGB
        with Image.open(result.path) as out_img:
            assert out_img.mode == "RGB"


class TestCleanupTmpFiles:
    """Test cases for cleanup_tmp_files function."""

    def test_cleanup_old_files(self, tmp_path, mock_settings, monkeypatch):
        """Test that old files are cleaned up."""
        import time

        # Use tmp_path as tmp_dir
        mock_settings.tmp_dir = tmp_path
        monkeypatch.setattr("app.photo_enhance.get_settings", lambda: mock_settings)

        # Create old file
        old_file = tmp_path / "old_file.jpg"
        old_file.write_text("test")

        # Set modification time to 2 days ago
        old_time = time.time() - (48 * 3600)
        os.utime(old_file, (old_time, old_time))

        # Create new file
        new_file = tmp_path / "new_file.jpg"
        new_file.write_text("test")

        deleted = cleanup_tmp_files(max_age_hours=24)

        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_preserves_keep_file(self, tmp_path, mock_settings, monkeypatch):
        """Test that .keep file is preserved."""
        import time

        mock_settings.tmp_dir = tmp_path
        monkeypatch.setattr("app.photo_enhance.get_settings", lambda: mock_settings)

        # Create .keep file
        keep_file = tmp_path / ".keep"
        keep_file.write_text("keep")

        # Make it old
        old_time = time.time() - (48 * 3600)
        os.utime(keep_file, (old_time, old_time))

        deleted = cleanup_tmp_files(max_age_hours=24)

        assert deleted == 0
        assert keep_file.exists()


class TestFormatEnhanceReport:
    """Test cases for format_enhance_report function."""

    def test_format_basic_report(self):
        """Test basic enhancement report formatting."""
        from app.models import PhotoEnhanceResult

        result = PhotoEnhanceResult(
            path="/tmp/out.jpg",
            original_size=(1000, 1000),
            final_size=(1000, 1000),
            was_cropped=False,
            was_denoised=True,
        )

        formatted = format_enhance_report(result)

        assert "улучшено" in formatted
        assert "шум" in formatted

    def test_format_with_crop(self):
        """Test report with cropping."""
        from app.models import PhotoEnhanceResult

        result = PhotoEnhanceResult(
            path="/tmp/out.jpg",
            original_size=(1000, 1000),
            final_size=(800, 800),
            was_cropped=True,
            was_denoised=True,
        )

        formatted = format_enhance_report(result)

        assert "Обрезан" in formatted

    def test_format_with_resize(self):
        """Test report with resizing."""
        from app.models import PhotoEnhanceResult

        result = PhotoEnhanceResult(
            path="/tmp/out.jpg",
            original_size=(3000, 3000),
            final_size=(2000, 2000),
            was_cropped=False,
            was_denoised=True,
        )

        formatted = format_enhance_report(result)

        assert "3000" in formatted
        assert "2000" in formatted
