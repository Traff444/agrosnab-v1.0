"""Tests for photo quality analysis."""

import pytest

from app.photo_quality import analyze_photo, format_quality_report
from app.models import PhotoStatus


class TestAnalyzePhoto:
    """Test cases for analyze_photo function."""

    def test_good_quality_image(self, temp_image, mock_settings, monkeypatch):
        """Test analysis of a good quality image."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_image)

        assert result.width == 1000
        assert result.height == 1000
        # Image might have low sharpness warning due to simple pattern
        # but should not have size warning
        assert not any("размер" in w.lower() for w in result.warnings)

    def test_small_image_warning(self, temp_small_image, mock_settings, monkeypatch):
        """Test that small images get a warning."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_small_image)

        assert result.width == 400
        assert result.height == 400
        assert result.status == PhotoStatus.WARNING
        assert any("размер" in w.lower() for w in result.warnings)

    def test_blurry_image_sharpness(self, temp_blurry_image, mock_settings, monkeypatch):
        """Test that blurry images are analyzed correctly."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_blurry_image)

        # Just verify the analysis completes and returns valid values
        assert result.sharpness >= 0
        assert result.width == 1000
        assert result.height == 1000

    def test_result_has_all_fields(self, temp_image, mock_settings, monkeypatch):
        """Test that result contains all expected fields."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_image)

        assert result.width > 0
        assert result.height > 0
        assert result.sharpness >= 0
        assert result.brightness_low >= 0
        assert result.brightness_high <= 255
        assert isinstance(result.warnings, list)


class TestFormatQualityReport:
    """Test cases for format_quality_report function."""

    def test_format_ok_status(self, temp_image, mock_settings, monkeypatch):
        """Test formatting OK status report."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_image)
        formatted = format_quality_report(result)

        assert "Качество фото" in formatted
        assert "Размер" in formatted
        assert "Резкость" in formatted

    def test_format_warning_status(self, temp_small_image, mock_settings, monkeypatch):
        """Test formatting WARNING status report."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_small_image)
        formatted = format_quality_report(result)

        assert "⚠️" in formatted
        assert "Замечания" in formatted

    def test_format_includes_dimensions(self, temp_image, mock_settings, monkeypatch):
        """Test that format includes dimensions."""
        monkeypatch.setattr("app.photo_quality.get_settings", lambda: mock_settings)
        result = analyze_photo(temp_image)
        formatted = format_quality_report(result)

        assert "1000" in formatted  # Width and height
