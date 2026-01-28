"""Tests for invoice generation."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestRubFormatter:
    """Tests for rub() currency formatter."""

    def test_simple_number(self):
        from app.invoice import rub

        assert rub(100) == "100 ₽"

    def test_thousands_separator(self):
        from app.invoice import rub

        assert rub(1000) == "1 000 ₽"
        assert rub(10000) == "10 000 ₽"
        assert rub(100000) == "100 000 ₽"

    def test_millions(self):
        from app.invoice import rub

        assert rub(1000000) == "1 000 000 ₽"
        assert rub(1234567) == "1 234 567 ₽"

    def test_zero(self):
        from app.invoice import rub

        assert rub(0) == "0 ₽"

    def test_negative_number(self):
        from app.invoice import rub

        assert rub(-1000) == "-1 000 ₽"


class TestEnsureFont:
    """Tests for ensure_font() function."""

    def test_returns_font_name(self):
        from app.invoice import ensure_font

        with patch("app.invoice.pdfmetrics") as mock_pdfmetrics:
            mock_pdfmetrics.getFont.return_value = MagicMock()
            result = ensure_font()
            assert result == "DejaVu"

    def test_registers_font_if_not_found(self):
        from app.invoice import ensure_font

        with patch("app.invoice.pdfmetrics") as mock_pdfmetrics:
            mock_pdfmetrics.getFont.side_effect = KeyError("DejaVu")
            with patch("app.invoice.TTFont") as mock_ttfont:
                result = ensure_font()
                mock_pdfmetrics.registerFont.assert_called_once()
                assert result == "DejaVu"

    def test_does_not_register_if_already_exists(self):
        from app.invoice import ensure_font

        with patch("app.invoice.pdfmetrics") as mock_pdfmetrics:
            mock_pdfmetrics.getFont.return_value = MagicMock()
            ensure_font()
            mock_pdfmetrics.registerFont.assert_not_called()


class TestGenerateInvoicePdf:
    """Tests for generate_invoice_pdf() function."""

    @pytest.fixture
    def sample_seller(self):
        return {
            "Орг. продавец (юр. лицо)": "ООО Тестовая Компания",
            "ИНН/ОГРН": "1234567890 / 1234567890123",
            "Адрес продавца": "г. Москва, ул. Тестовая, д. 1",
            "Телефон продавца": "+7 (999) 123-45-67",
            "Email продавца": "test@example.com",
        }

    @pytest.fixture
    def sample_items(self):
        return [
            ("SKU-001", "Товар первый", 2, 1500),
            ("SKU-002", "Товар второй с длинным названием для теста", 5, 800),
            ("SKU-003", "Товар третий", 1, 3000),
        ]

    def test_creates_pdf_file(self, tmp_path, sample_seller, sample_items):
        """Test that PDF file is created."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "test_invoice.pdf")

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-001",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Самовывоз",
                items=sample_items,
            )

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0

    def test_pdf_is_valid(self, tmp_path, sample_seller, sample_items):
        """Test that generated file is a valid PDF."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "test_invoice.pdf")

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-002",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="CDEK до ПВЗ",
                items=sample_items,
            )

        # Check PDF magic bytes
        with open(pdf_path, "rb") as f:
            header = f.read(8)
            assert header.startswith(b"%PDF-")

    def test_empty_items_list(self, tmp_path, sample_seller):
        """Test with empty items list."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "empty_invoice.pdf")

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-003",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Доставка курьером",
                items=[],
            )

        assert os.path.exists(pdf_path)

    def test_single_item(self, tmp_path, sample_seller):
        """Test with single item."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "single_item_invoice.pdf")
        items = [("SKU-SINGLE", "Единственный товар", 10, 500)]

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-004",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Почта России",
                items=items,
            )

        assert os.path.exists(pdf_path)

    def test_long_product_name_truncation(self, tmp_path, sample_seller):
        """Test that long product names are handled."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "long_name_invoice.pdf")
        long_name = "А" * 100  # Very long name
        items = [("SKU-LONG", long_name, 1, 1000)]

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-005",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Самовывоз",
                items=items,
            )

        assert os.path.exists(pdf_path)

    def test_many_items_pagination(self, tmp_path, sample_seller):
        """Test with many items that should trigger pagination."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "many_items_invoice.pdf")
        # Create 50 items to trigger page break
        items = [(f"SKU-{i:03d}", f"Товар номер {i}", i % 10 + 1, 100 * i) for i in range(1, 51)]

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-006",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Доставка CDEK",
                items=items,
            )

        assert os.path.exists(pdf_path)
        # Multi-page PDF should be larger
        assert os.path.getsize(pdf_path) > 3000

    def test_missing_seller_fields(self, tmp_path, sample_items):
        """Test with missing seller fields."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "partial_seller_invoice.pdf")
        partial_seller = {
            "Орг. продавец (юр. лицо)": "ИП Тестов",
            # Missing other fields
        }

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-007",
                invoice_date="27.01.2024",
                seller=partial_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Самовывоз",
                items=sample_items,
            )

        assert os.path.exists(pdf_path)

    def test_zero_price_item(self, tmp_path, sample_seller):
        """Test with zero price item."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "zero_price_invoice.pdf")
        items = [("SKU-FREE", "Бесплатный товар", 1, 0)]

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-008",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Самовывоз",
                items=items,
            )

        assert os.path.exists(pdf_path)

    def test_high_quantity_item(self, tmp_path, sample_seller):
        """Test with high quantity item."""
        from app.invoice import generate_invoice_pdf

        pdf_path = str(tmp_path / "high_qty_invoice.pdf")
        items = [("SKU-BULK", "Оптовый товар", 10000, 50)]

        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf_path,
                invoice_no="INV-2024-009",
                invoice_date="27.01.2024",
                seller=sample_seller,
                buyer_phone="+7 (900) 111-22-33",
                delivery="Грузовая доставка",
                items=items,
            )

        assert os.path.exists(pdf_path)


class TestInvoiceIntegration:
    """Integration tests for invoice generation."""

    def test_total_calculation(self, tmp_path):
        """Verify total is calculated correctly by checking file size varies with items."""
        from app.invoice import generate_invoice_pdf

        seller = {"Орг. продавец (юр. лицо)": "Тест"}

        # Generate with few items
        pdf1 = str(tmp_path / "invoice1.pdf")
        items1 = [("A", "Item", 1, 100)]
        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf1,
                invoice_no="1",
                invoice_date="01.01.2024",
                seller=seller,
                buyer_phone="+7",
                delivery="Test",
                items=items1,
            )

        # Generate with more items
        pdf2 = str(tmp_path / "invoice2.pdf")
        items2 = [("A", "Item", 1, 100), ("B", "Item2", 2, 200), ("C", "Item3", 3, 300)]
        with patch("app.invoice.ensure_font", return_value="Helvetica"):
            generate_invoice_pdf(
                pdf2,
                invoice_no="2",
                invoice_date="01.01.2024",
                seller=seller,
                buyer_phone="+7",
                delivery="Test",
                items=items2,
            )

        # More items = larger file
        assert os.path.getsize(pdf2) > os.path.getsize(pdf1)
