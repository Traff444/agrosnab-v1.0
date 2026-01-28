"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment variables before importing app modules
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("OWNER_TELEGRAM_IDS", "123456789")
os.environ.setdefault("GOOGLE_SHEETS_ID", "test_sheet_id")
os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "/tmp/test.json")
os.environ.setdefault("DRIVE_FOLDER_ID", "test_folder_id")


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for tests."""
    from app.config import Settings

    settings = Settings(
        telegram_bot_token="test_token",
        owner_telegram_ids=[123456789, 987654321],
        google_sheets_id="test_sheet_id",
        google_service_account_json_path="/tmp/test.json",
        drive_folder_id="test_folder_id",
        photo_min_size=800,
        photo_sharpness_threshold=100.0,
        photo_brightness_min=40,
        photo_brightness_max=220,
    )

    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    return settings


@pytest.fixture
def sample_product():
    """Create a sample product for tests."""
    from app.models import Product

    return Product(
        row_number=2,
        sku="PRD-20240101-ABCD",
        name="Test Product",
        price=500.0,
        stock=10,
        photo_url="https://example.com/photo.jpg",
        description="Test description",
        tags="test,sample",
        active=True,
    )


@pytest.fixture
def sample_intake_session():
    """Create a sample intake session."""
    from app.models import IntakeSession

    return IntakeSession(
        user_id=123456789,
        name="New Product",
        price=1000.0,
        quantity=5,
    )


@pytest.fixture
def mock_sheets_client(monkeypatch):
    """Mock Google Sheets client."""
    mock = MagicMock()
    mock.load_column_map = AsyncMock(return_value={
        "SKU": 0,
        "Наименование": 1,
        "Цена": 2,
        "Остаток": 3,
        "Фото": 4,
        "Активен": 5,
    })
    mock.get_all_products = AsyncMock(return_value=[])
    mock.search_products = AsyncMock(return_value=[])
    mock.find_product_by_sku = AsyncMock(return_value=None)
    mock.create_product = AsyncMock()
    mock.update_product_stock = AsyncMock()
    mock.update_product_photo = AsyncMock()

    monkeypatch.setattr("app.sheets.sheets_client", mock)
    return mock


@pytest.fixture
def mock_drive_client(monkeypatch):
    """Mock Google Drive client."""
    from app.models import DriveUploadResult

    mock = MagicMock()
    mock.upload_photo = AsyncMock(return_value=DriveUploadResult(
        file_id="test_file_id",
        public_url="https://drive.google.com/uc?export=view&id=test_file_id",
        permissions_ok=True,
    ))
    mock.delete_photo = AsyncMock(return_value=True)
    mock.test_connection = AsyncMock(return_value={"ok": True})

    monkeypatch.setattr("app.drive.drive_client", mock)
    return mock


@pytest.fixture
def temp_image(tmp_path):
    """Create a temporary test image."""
    from PIL import Image

    img_path = tmp_path / "test_image.jpg"
    img = Image.new("RGB", (1000, 1000), color="white")

    # Add some variation for sharpness detection
    pixels = img.load()
    for i in range(0, 1000, 10):
        for j in range(0, 1000, 10):
            pixels[i, j] = (0, 0, 0)

    img.save(img_path, "JPEG", quality=95)
    return str(img_path)


@pytest.fixture
def temp_blurry_image(tmp_path):
    """Create a temporary blurry test image."""
    from PIL import Image, ImageFilter

    img_path = tmp_path / "blurry_image.jpg"
    img = Image.new("RGB", (1000, 1000), color="gray")
    img = img.filter(ImageFilter.GaussianBlur(radius=10))
    img.save(img_path, "JPEG", quality=95)
    return str(img_path)


@pytest.fixture
def temp_small_image(tmp_path):
    """Create a small test image."""
    from PIL import Image

    img_path = tmp_path / "small_image.jpg"
    img = Image.new("RGB", (400, 400), color="white")
    img.save(img_path, "JPEG", quality=95)
    return str(img_path)
