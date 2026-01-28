"""Tests for Google Sheets client."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock google modules before importing app modules
sys.modules["google"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.service_account"] = MagicMock()
googleapiclient_mock = MagicMock()
sys.modules["googleapiclient"] = googleapiclient_mock
sys.modules["googleapiclient.discovery"] = MagicMock()

# Create mock HttpError
mock_http_error_module = MagicMock()


class MockHttpError(Exception):
    """Mock HttpError for testing."""

    def __init__(self, status):
        self.resp = MagicMock()
        self.resp.status = status
        super().__init__(f"HttpError {status}")


mock_http_error_module.HttpError = MockHttpError
sys.modules["googleapiclient.errors"] = mock_http_error_module


class TestConvertPhotoUrl:
    """Tests for convert_photo_url() function."""

    def test_empty_url(self):
        from app.sheets import convert_photo_url

        assert convert_photo_url("") == ""
        assert convert_photo_url("   ") == ""

    def test_none_like_empty(self):
        from app.sheets import convert_photo_url

        # Function expects str, but should handle empty
        assert convert_photo_url("") == ""

    def test_google_drive_file_url(self):
        from app.sheets import convert_photo_url

        url = "https://drive.google.com/file/d/1abc123XYZ/view?usp=sharing"
        result = convert_photo_url(url)
        assert result == "https://drive.google.com/uc?export=view&id=1abc123XYZ"

    def test_google_drive_already_converted(self):
        from app.sheets import convert_photo_url

        url = "https://drive.google.com/uc?export=view&id=1abc123XYZ"
        result = convert_photo_url(url)
        assert result == url

    def test_dropbox_url(self):
        from app.sheets import convert_photo_url

        url = "https://www.dropbox.com/s/abc123/photo.jpg?dl=0"
        result = convert_photo_url(url)
        assert result == "https://www.dropbox.com/s/abc123/photo.jpg?dl=1"

    def test_dropbox_url_already_dl1(self):
        from app.sheets import convert_photo_url

        url = "https://www.dropbox.com/s/abc123/photo.jpg?dl=1"
        result = convert_photo_url(url)
        assert result == url

    def test_regular_url_unchanged(self):
        from app.sheets import convert_photo_url

        url = "https://example.com/images/photo.jpg"
        result = convert_photo_url(url)
        assert result == url

    def test_strips_whitespace(self):
        from app.sheets import convert_photo_url

        url = "  https://example.com/photo.jpg  "
        result = convert_photo_url(url)
        assert result == "https://example.com/photo.jpg"

    def test_google_drive_with_different_id_formats(self):
        from app.sheets import convert_photo_url

        # ID with underscores
        url = "https://drive.google.com/file/d/1abc_123-XYZ/view"
        result = convert_photo_url(url)
        assert "1abc_123-XYZ" in result

        # ID with dashes
        url2 = "https://drive.google.com/file/d/abc-def-123/view"
        result2 = convert_photo_url(url2)
        assert "abc-def-123" in result2


class TestRetryAsync:
    """Tests for retry_async() function."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        from app.sheets import retry_async

        async def success_fn():
            return "result"

        result = await retry_async(success_fn, retries=3, delay=0.01)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        from app.sheets import retry_async

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"

        result = await retry_async(fail_then_succeed, retries=3, delay=0.01)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        from app.sheets import retry_async

        async def always_fail():
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            await retry_async(always_fail, retries=3, delay=0.01)

    @pytest.mark.asyncio
    async def test_http_error_429_retries(self):
        from app.sheets import retry_async

        call_count = 0

        async def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise MockHttpError(429)
            return "success"

        result = await retry_async(rate_limited, retries=3, delay=0.01)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_http_error_500_retries(self):
        from app.sheets import retry_async

        call_count = 0

        async def server_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise MockHttpError(500)
            return "recovered"

        result = await retry_async(server_error, retries=3, delay=0.01)
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_http_error_503_retries(self):
        from app.sheets import retry_async

        call_count = 0

        async def unavailable():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise MockHttpError(503)
            return "available"

        result = await retry_async(unavailable, retries=3, delay=0.01)
        assert result == "available"

    @pytest.mark.asyncio
    async def test_http_error_404_no_retry(self):
        from app.sheets import retry_async

        async def not_found():
            raise MockHttpError(404)

        with pytest.raises(MockHttpError):
            await retry_async(not_found, retries=3, delay=0.01)

    @pytest.mark.asyncio
    async def test_with_arguments(self):
        from app.sheets import retry_async

        async def add(a, b):
            return a + b

        result = await retry_async(add, 2, 3, retries=3, delay=0.01)
        assert result == 5

    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        from app.sheets import retry_async

        async def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = await retry_async(greet, "World", greeting="Hi", retries=3, delay=0.01)
        assert result == "Hi, World!"


class TestSheetsClientGetProducts:
    """Tests for SheetsClient.get_products() method."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            # Create client with mocked dependencies
            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    def test_get_products_basic(self, mock_sheets_client):
        """Test basic product parsing."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Остаток", "Теги", "Фото_URL"],
            ["PRD-001", "Товар 1", "1000", "50", "категория1", "https://example.com/1.jpg"],
            ["PRD-002", "Товар 2", "2000", "30", "категория2", ""],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()

        assert len(products) == 2
        assert products[0]["sku"] == "PRD-001"
        assert products[0]["name"] == "Товар 1"
        assert products[0]["price_rub"] == 1000
        assert products[0]["stock"] == 50
        assert products[0]["tags"] == "категория1"

    def test_get_products_empty_sheet(self, mock_sheets_client):
        """Test with empty sheet."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.return_value = {"values": []}

        products = client.get_products()
        assert products == []

    def test_get_products_header_only(self, mock_sheets_client):
        """Test with only header row."""
        client, mock_service = mock_sheets_client

        mock_values = [["SKU", "Наименование", "Цена"]]
        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        assert products == []

    def test_get_products_flexible_column_names(self, mock_sheets_client):
        """Test flexible column name matching."""
        client, mock_service = mock_sheets_client

        # Different column naming style
        mock_values = [
            ["Артикул", "Название", "Стоимость", "Stock", "Tags"],
            ["SKU-1", "Product", "500", "10", "tag"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        assert len(products) == 1
        assert products[0]["sku"] == "SKU-1"
        assert products[0]["name"] == "Product"
        assert products[0]["price_rub"] == 500

    def test_get_products_with_active_column(self, mock_sheets_client):
        """Test filtering by Активен column."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Активен"],
            ["PRD-001", "Active", "100", "да"],
            ["PRD-002", "Inactive", "200", "нет"],
            ["PRD-003", "AlsoActive", "300", "yes"],
            ["PRD-004", "InactiveToo", "400", "false"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        skus = [p["sku"] for p in products]

        assert "PRD-001" in skus
        assert "PRD-003" in skus
        assert "PRD-002" not in skus
        assert "PRD-004" not in skus

    def test_get_products_price_parsing(self, mock_sheets_client):
        """Test various price formats."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена"],
            ["P1", "Normal", "1000"],
            ["P2", "WithSpaces", "1 000"],
            ["P3", "WithRuble", "2000₽"],
            ["P4", "Decimal", "1500.50"],
            ["P5", "Invalid", "abc"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()

        prices = {p["sku"]: p["price_rub"] for p in products}
        assert prices["P1"] == 1000
        assert prices["P2"] == 1000
        assert prices["P3"] == 2000
        assert prices["P4"] == 1500
        assert prices["P5"] == 0  # Invalid defaults to 0

    def test_get_products_google_drive_photo_conversion(self, mock_sheets_client):
        """Test photo URL conversion."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Фото"],
            ["P1", "GDrive", "100", "https://drive.google.com/file/d/abc123/view"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        assert "uc?export=view" in products[0]["photo_url"]

    def test_get_products_missing_required_columns(self, mock_sheets_client):
        """Test with missing required columns."""
        client, mock_service = mock_sheets_client

        # Missing SKU column
        mock_values = [
            ["Наименование", "Цена"],
            ["Product", "100"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        assert products == []

    def test_get_products_api_error(self, mock_sheets_client):
        """Test handling of API errors."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.side_effect = Exception("API Error")

        products = client.get_products()
        assert products == []

    def test_get_products_skip_empty_sku(self, mock_sheets_client):
        """Test that rows with empty SKU are skipped."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена"],
            ["PRD-001", "Valid", "100"],
            ["", "NoSKU", "200"],
            ["PRD-002", "AlsoValid", "300"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        products = client.get_products()
        assert len(products) == 2
        assert all(p["sku"] for p in products)


class TestSheetsClientGetSettings:
    """Tests for SheetsClient.get_settings() method."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    def test_get_settings_basic(self, mock_sheets_client):
        """Test basic settings parsing."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["Мин. сумма заказа", "5000"],
            ["Компания", "ООО Тест"],
            ["Email", "test@example.com"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        settings = client.get_settings()

        assert settings["Мин. сумма заказа"] == "5000"
        assert settings["Компания"] == "ООО Тест"
        assert settings["Email"] == "test@example.com"

    def test_get_settings_empty(self, mock_sheets_client):
        """Test with empty settings."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.return_value = {"values": []}

        settings = client.get_settings()
        assert settings == {}

    def test_get_settings_skip_incomplete_rows(self, mock_sheets_client):
        """Test that incomplete rows are skipped."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["Key1", "Value1"],
            ["KeyOnly"],  # Missing value
            ["Key2", "Value2"],
            ["", "ValueOnly"],  # Empty key
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        settings = client.get_settings()
        assert "Key1" in settings
        assert "Key2" in settings
        assert "KeyOnly" not in settings
        assert "" not in settings


class TestSheetsClientGetCategories:
    """Tests for SheetsClient.get_categories() method."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    def test_get_categories_basic(self, mock_sheets_client):
        """Test basic category extraction."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Теги"],
            ["P1", "Product1", "100", "категория1,категория2"],
            ["P2", "Product2", "200", "категория2,категория3"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        categories = client.get_categories()

        assert "категория1" in categories
        assert "категория2" in categories
        assert "категория3" in categories
        assert len(categories) == 3

    def test_get_categories_sorted(self, mock_sheets_client):
        """Test that categories are sorted."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Теги"],
            ["P1", "Product", "100", "zebra,apple,banana"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        categories = client.get_categories()
        assert categories == ["apple", "banana", "zebra"]

    def test_get_categories_empty_tags(self, mock_sheets_client):
        """Test with no tags."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Теги"],
            ["P1", "Product", "100", ""],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        categories = client.get_categories()
        assert categories == []

    def test_get_categories_strips_whitespace(self, mock_sheets_client):
        """Test that whitespace is stripped from tags."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Цена", "Теги"],
            ["P1", "Product", "100", "  tag1  ,  tag2  "],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        categories = client.get_categories()
        assert "tag1" in categories
        assert "tag2" in categories
        assert "  tag1  " not in categories


class TestSheetsClientDecreaseStock:
    """Tests for SheetsClient.decrease_stock() method."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    @pytest.mark.asyncio
    async def test_decrease_stock_empty_list(self, mock_sheets_client):
        """Test with empty SKU list."""
        client, mock_service = mock_sheets_client

        # Should return early without API calls
        await client.decrease_stock([])

        mock_service.spreadsheets().values().get.assert_not_called()

    @pytest.mark.asyncio
    async def test_decrease_stock_no_rows(self, mock_sheets_client):
        """Test with no data rows."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.return_value = {"values": []}

        await client.decrease_stock([("SKU-1", 5)])

        # Should not attempt batch update
        mock_service.spreadsheets().values().batchUpdate.assert_not_called()

    @pytest.mark.asyncio
    async def test_decrease_stock_basic(self, mock_sheets_client):
        """Test basic stock decrease."""
        client, mock_service = mock_sheets_client

        mock_values = [
            ["SKU", "Наименование", "Списано"],
            ["PRD-001", "Product1", "10"],
            ["PRD-002", "Product2", "5"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        await client.decrease_stock([("PRD-001", 3)])

        # Verify batch update was called
        mock_service.spreadsheets().values().batchUpdate.assert_called_once()

    @pytest.mark.asyncio
    async def test_decrease_stock_missing_columns(self, mock_sheets_client):
        """Test when required columns are missing."""
        client, mock_service = mock_sheets_client

        # Missing Списано column
        mock_values = [
            ["SKU", "Наименование", "Цена"],
            ["PRD-001", "Product1", "100"],
        ]

        mock_service.spreadsheets().values().get().execute.return_value = {"values": mock_values}

        await client.decrease_stock([("PRD-001", 3)])

        # Should not attempt batch update
        mock_service.spreadsheets().values().batchUpdate.assert_not_called()


class TestSheetsClientAsyncMethods:
    """Tests for async wrapper methods."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    @pytest.mark.asyncio
    async def test_get_values_async(self, mock_sheets_client):
        """Test async get_values wrapper."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["A", "B"], ["1", "2"]]
        }

        result = await client.get_values("Sheet!A1:B2")

        assert result == [["A", "B"], ["1", "2"]]

    @pytest.mark.asyncio
    async def test_append_values_async(self, mock_sheets_client):
        """Test async append_values wrapper."""
        client, mock_service = mock_sheets_client

        await client.append_values("Sheet!A1", [["value1", "value2"]])

        mock_service.spreadsheets().values().append.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_values_async(self, mock_sheets_client):
        """Test async update_values wrapper."""
        client, mock_service = mock_sheets_client

        await client.update_values("Sheet!A1", [["new_value"]])

        mock_service.spreadsheets().values().update.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_order_async(self, mock_sheets_client):
        """Test async append_order wrapper."""
        client, mock_service = mock_sheets_client

        order_row = ["order_id", "user", "100", "2024-01-27"]
        await client.append_order(order_row)

        mock_service.spreadsheets().values().append.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_spisanie_rows_async(self, mock_sheets_client):
        """Test async append_spisanie_rows wrapper."""
        client, mock_service = mock_sheets_client

        rows = [["SKU-1", "5"], ["SKU-2", "3"]]
        await client.append_spisanie_rows(rows)

        mock_service.spreadsheets().values().append.assert_called_once()


class TestSheetsClientSyncMethods:
    """Tests for sync methods."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    def test_get_values_sync(self, mock_sheets_client):
        """Test sync get_values_sync method."""
        client, mock_service = mock_sheets_client

        mock_service.spreadsheets().values().get().execute.return_value = {"values": [["test"]]}

        result = client.get_values_sync("Sheet!A1")
        assert result == [["test"]]

    def test_append_values_sync(self, mock_sheets_client):
        """Test sync append_values_sync method."""
        client, mock_service = mock_sheets_client

        client.append_values_sync("Sheet!A1", [["data"]])

        mock_service.spreadsheets().values().append.assert_called_once()

    def test_update_values_sync(self, mock_sheets_client):
        """Test sync update_values_sync method."""
        client, mock_service = mock_sheets_client

        client.update_values_sync("Sheet!A1", [["updated"]])

        mock_service.spreadsheets().values().update.assert_called_once()

    def test_append_order_sync(self, mock_sheets_client):
        """Test sync append_order_sync method."""
        client, mock_service = mock_sheets_client

        client.append_order_sync(["order_data"])

        mock_service.spreadsheets().values().append.assert_called_once()

    def test_append_spisanie_rows_sync(self, mock_sheets_client):
        """Test sync append_spisanie_rows_sync method."""
        client, mock_service = mock_sheets_client

        client.append_spisanie_rows_sync([["row1"], ["row2"]])

        mock_service.spreadsheets().values().append.assert_called_once()


class TestSheetsClientBatchUpdate:
    """Tests for batch update methods."""

    @pytest.fixture
    def mock_sheets_client(self):
        """Create a mocked SheetsClient."""
        with patch("app.sheets.Credentials") as mock_creds, patch("app.sheets.build") as mock_build:
            mock_creds.from_service_account_file.return_value = MagicMock()
            mock_service = MagicMock()
            mock_build.return_value = mock_service

            from app.sheets import SheetsClient

            with patch("pathlib.Path"):
                client = SheetsClient("test_spreadsheet_id", "/fake/path.json")

            yield client, mock_service

    def test_batch_update_sync_empty(self, mock_sheets_client):
        """Test batch update with empty data."""
        client, mock_service = mock_sheets_client

        client._batch_update_values_sync([])

        mock_service.spreadsheets().values().batchUpdate.assert_not_called()

    def test_batch_update_sync_with_data(self, mock_sheets_client):
        """Test batch update with data."""
        client, mock_service = mock_sheets_client

        data = [
            {"range": "Sheet!A1", "values": [[1]]},
            {"range": "Sheet!B1", "values": [[2]]},
        ]

        client._batch_update_values_sync(data)

        mock_service.spreadsheets().values().batchUpdate.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_update_async(self, mock_sheets_client):
        """Test async batch update."""
        client, mock_service = mock_sheets_client

        data = [{"range": "Sheet!A1", "values": [[1]]}]

        await client.batch_update_values(data)

        mock_service.spreadsheets().values().batchUpdate.assert_called_once()
