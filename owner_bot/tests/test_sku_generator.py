"""Tests for SKU generation."""

import re
from datetime import datetime


class TestSKUGeneration:
    """Test cases for SKU generation in sheets client."""

    def test_sku_format(self, mock_sheets_client):
        """Test that SKU follows expected format."""
        from app.sheets import SheetsClient

        client = SheetsClient()
        sku = client._generate_sku()

        # Format: PRD-YYYYMMDD-XXXX
        pattern = r"^PRD-\d{8}-[A-F0-9]{4}$"
        assert re.match(pattern, sku), f"SKU {sku} doesn't match expected format"

    def test_sku_contains_current_date(self, mock_sheets_client):
        """Test that SKU contains current date."""
        from app.sheets import SheetsClient

        client = SheetsClient()
        sku = client._generate_sku()

        today = datetime.now().strftime("%Y%m%d")
        assert today in sku

    def test_sku_uniqueness(self, mock_sheets_client):
        """Test that multiple SKUs are mostly unique."""
        from app.sheets import SheetsClient

        client = SheetsClient()

        skus = set()
        for _ in range(100):
            sku = client._generate_sku()
            skus.add(sku)

        # Allow for rare collisions (4 hex chars = 65536 possibilities)
        # With 100 iterations, collision is unlikely but possible
        assert len(skus) >= 98

    def test_sku_hex_portion_is_uppercase(self, mock_sheets_client):
        """Test that hex portion is uppercase."""
        from app.sheets import SheetsClient

        client = SheetsClient()
        sku = client._generate_sku()

        hex_part = sku.split("-")[-1]
        assert hex_part == hex_part.upper()
        assert len(hex_part) == 4
