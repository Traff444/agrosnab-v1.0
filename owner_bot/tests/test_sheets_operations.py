"""Tests for Google Sheets operations."""

from unittest.mock import MagicMock

import pytest


class TestColumnMapping:
    """Test cases for column mapping functionality."""

    def test_col_letter_single(self):
        """Test single letter column conversion."""
        from app.sheets import SheetsClient

        client = SheetsClient()

        assert client._col_letter(0) == "A"
        assert client._col_letter(1) == "B"
        assert client._col_letter(25) == "Z"

    def test_col_letter_double(self):
        """Test double letter column conversion."""
        from app.sheets import SheetsClient

        client = SheetsClient()

        assert client._col_letter(26) == "AA"
        assert client._col_letter(27) == "AB"
        assert client._col_letter(51) == "AZ"
        assert client._col_letter(52) == "BA"

    def test_row_to_dict(self):
        """Test row list to dict conversion."""
        from app.sheets import SheetsClient

        client = SheetsClient()
        client._col_map = {
            "SKU": 0,
            "Наименование": 1,
            "Цена": 2,
            "Остаток": 3,
        }

        row = ["PRD-001", "Test Product", 500, 10]
        result = client._row_to_dict(row)

        assert result["SKU"] == "PRD-001"
        assert result["Наименование"] == "Test Product"
        assert result["Цена"] == 500
        assert result["Остаток"] == 10

    def test_row_to_dict_short_row(self):
        """Test conversion of row shorter than column map."""
        from app.sheets import SheetsClient

        client = SheetsClient()
        client._col_map = {
            "SKU": 0,
            "Наименование": 1,
            "Цена": 2,
            "Остаток": 3,
        }

        # Row is missing last column
        row = ["PRD-001", "Test"]
        result = client._row_to_dict(row)

        assert result["SKU"] == "PRD-001"
        assert result["Наименование"] == "Test"
        assert result["Цена"] == ""  # Missing columns get empty string
        assert result["Остаток"] == ""


class TestProductFromRow:
    """Test Product.from_row class method."""

    def test_product_from_row(self):
        """Test creating product from row data."""
        from app.models import Product

        data = {
            "SKU": "PRD-20240101-ABCD",
            "Наименование": "Test Product",
            "Цена": 500,
            "Остаток": 10,
            "Фото": "https://example.com/photo.jpg",
            "Активен": "TRUE",
            "Теги": "tag1,tag2",
            "Описание_кратко": "Short desc",
        }

        col_map = {"SKU": 0, "Наименование": 1}  # Minimal col_map

        product = Product.from_row(2, data, col_map)

        assert product.row_number == 2
        assert product.sku == "PRD-20240101-ABCD"
        assert product.name == "Test Product"
        assert product.price == 500.0
        assert product.stock == 10
        assert product.active is True

    def test_product_from_row_inactive(self):
        """Test creating inactive product."""
        from app.models import Product

        data = {
            "SKU": "PRD-001",
            "Наименование": "Inactive",
            "Цена": 100,
            "Остаток": 0,
            "Фото": "",
            "Активен": "FALSE",
        }

        product = Product.from_row(3, data, {})

        assert product.active is False

    def test_product_from_row_missing_values(self):
        """Test creating product with missing values."""
        from app.models import Product

        data = {
            "SKU": "PRD-001",
            "Наименование": "Minimal",
            # Missing other fields
        }

        product = Product.from_row(4, data, {})

        assert product.price == 0.0
        assert product.stock == 0
        assert product.photo_url == ""


class TestSearchProducts:
    """Test product search functionality."""

    @pytest.mark.asyncio
    async def test_search_by_name(self):
        """Test searching products by name."""
        from app.sheets import SheetsClient

        # Create client and mock its service
        client = SheetsClient()
        client._col_map = {
            "SKU": 0,
            "Наименование": 1,
            "Цена": 2,
            "Остаток": 3,
            "Фото": 4,
            "Активен": 5,
        }

        # Mock the get method
        mock_service = MagicMock()
        mock_values = MagicMock()
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "values": [
                ["PRD-001", "Coffee Arabica", 500, 10, "", "TRUE"],
                ["PRD-002", "Coffee Robusta", 400, 15, "", "TRUE"],
                ["PRD-003", "Tea Earl Grey", 300, 20, "", "TRUE"],
            ]
        }
        mock_values.get.return_value = mock_get
        mock_service.spreadsheets.return_value.values.return_value = mock_values
        client._service = mock_service

        results = await client.search_products("Coffee")

        assert len(results) == 2
        assert all("Coffee" in p.name for p in results)
