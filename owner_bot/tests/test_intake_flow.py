"""Tests for intake flow and service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.intake_parser import parse_intake_string
from app.models import IntakeConfidence


class TestIntakeParserWeight:
    """Test cases for intake parser with weight support."""

    def test_parse_quick_string_with_weight(self):
        """Test parsing quick string with weight in grams."""
        result = parse_intake_string("Махорка СССР 50г 500 10")

        assert result.name == "Махорка СССР"
        assert result.weight == 50
        assert result.price == 500.0
        assert result.quantity == 10
        assert result.confidence == IntakeConfidence.HIGH

    def test_parse_quick_string_with_weight_g_latin(self):
        """Test parsing weight with latin 'g' suffix."""
        result = parse_intake_string("Product 100g 200 5")

        assert result.name == "Product"
        assert result.weight == 100
        assert result.price == 200.0
        assert result.quantity == 5

    def test_parse_quick_string_without_weight(self):
        """Test parsing quick string without weight (backward compatibility)."""
        result = parse_intake_string("Махорка СССР 500 10")

        assert result.name == "Махорка СССР"
        assert result.weight is None
        assert result.price == 500.0
        assert result.quantity == 10
        assert result.confidence == IntakeConfidence.HIGH

    def test_parse_quick_string_weight_with_space(self):
        """Test parsing weight with space before suffix."""
        result = parse_intake_string("Товар 50 г 300 15")

        assert result.name == "Товар"
        assert result.weight == 50
        assert result.price == 300.0
        assert result.quantity == 15

    def test_parse_only_name_with_weight(self):
        """Test parsing name with weight only."""
        result = parse_intake_string("Новый товар 200г")

        assert result.name == "Новый товар"
        assert result.weight == 200
        assert result.confidence == IntakeConfidence.LOW

    def test_parse_weight_at_various_positions(self):
        """Test that weight is extracted correctly regardless of position."""
        result = parse_intake_string("Табак 500 100г 10")

        # Weight should be extracted by suffix, not position
        assert result.weight == 100
        assert result.name == "Табак"
        # price and qty extracted from remaining numbers
        assert result.price == 500.0
        assert result.quantity == 10

    def test_parse_realistic_product_names(self):
        """Test realistic product names with weight."""
        test_cases = [
            ("Махорка Дедушкина 50г 450 20", "Махорка Дедушкина", 50, 450.0, 20),
            ("Самосад крупный 100г 800 5", "Самосад крупный", 100, 800.0, 5),
            ("Табак Вирджиния 25г 300 30", "Табак Вирджиния", 25, 300.0, 30),
        ]

        for input_str, exp_name, exp_weight, exp_price, exp_qty in test_cases:
            result = parse_intake_string(input_str)
            assert result.name == exp_name, f"Failed for: {input_str}"
            assert result.weight == exp_weight, f"Failed for: {input_str}"
            assert result.price == exp_price, f"Failed for: {input_str}"
            assert result.quantity == exp_qty, f"Failed for: {input_str}"


class TestIntakeSession:
    """Test cases for IntakeSession model."""

    def test_compute_fingerprint(self, sample_intake_session):
        """Test fingerprint computation."""
        fp1 = sample_intake_session.compute_fingerprint()

        assert fp1 is not None
        assert len(fp1) == 16  # SHA256 truncated to 16 chars

    def test_fingerprint_changes_with_data(self, sample_intake_session):
        """Test that fingerprint changes when data changes."""
        fp1 = sample_intake_session.compute_fingerprint()

        sample_intake_session.name = "Different Name"
        fp2 = sample_intake_session.compute_fingerprint()

        assert fp1 != fp2

    def test_fingerprint_consistent(self, sample_intake_session):
        """Test that same data produces same fingerprint."""
        fp1 = sample_intake_session.compute_fingerprint()
        fp2 = sample_intake_session.compute_fingerprint()

        assert fp1 == fp2


class TestIntakeService:
    """Test cases for IntakeService."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test session creation."""
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()

        with patch("app.services.intake_service.intake_session_store", mock_store):
            session = await service.create_session(123456789)

        assert session is not None
        assert session.user_id == 123456789
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test session retrieval."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        expected_session = IntakeSession(user_id=123456789)
        mock_store = MagicMock()
        mock_store.get = AsyncMock(return_value=expected_session)

        service = IntakeService()

        with patch("app.services.intake_service.intake_session_store", mock_store):
            session = await service.get_session(123456789)

        assert session is not None
        assert session.user_id == 123456789
        mock_store.get.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test retrieval of nonexistent session."""
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.get = AsyncMock(return_value=None)

        service = IntakeService()

        with patch("app.services.intake_service.intake_session_store", mock_store):
            session = await service.get_session(999999)

        assert session is None

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """Test session clearing."""
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.delete = AsyncMock(return_value=True)

        service = IntakeService()

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.clear_session(123456789)

        mock_store.delete.assert_called_once_with(123456789)

    @pytest.mark.asyncio
    async def test_update_session_from_parsed(self):
        """Test updating session from parsed intake."""
        from app.models import IntakeConfidence, IntakeSession, ParsedIntake
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()
        session = IntakeSession(user_id=123456789)

        parsed = ParsedIntake(
            name="Test Product",
            price=500.0,
            quantity=10,
            confidence=IntakeConfidence.HIGH,
            raw_input="Test Product 500 10",
        )

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.update_session_from_parsed(session, parsed)

        assert session.name == "Test Product"
        assert session.price == 500.0
        assert session.quantity == 10
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_from_parsed_with_weight(self):
        """Test updating session from parsed intake with weight."""
        from app.models import IntakeConfidence, IntakeSession, ParsedIntake
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()
        session = IntakeSession(user_id=123456789)

        parsed = ParsedIntake(
            name="Product with Weight",
            price=500.0,
            quantity=10,
            weight=50,
            confidence=IntakeConfidence.HIGH,
            raw_input="Product with Weight 50г 500 10",
        )

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.update_session_from_parsed(session, parsed)

        assert session.name == "Product with Weight"
        assert session.price == 500.0
        assert session.quantity == 10
        assert session.package_weight == 50
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_existing_product(self, sample_product):
        """Test setting existing product in session."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()
        session = IntakeSession(user_id=123456789)

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.set_existing_product(session, sample_product)

        assert session.existing_product == sample_product
        assert session.is_new_product is False
        assert session.sku == sample_product.sku
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_new_product(self, sample_product):
        """Test setting session for new product."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()
        session = IntakeSession(user_id=123456789)

        # Set as existing first
        session.existing_product = sample_product
        session.is_new_product = False
        session.sku = sample_product.sku

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.set_new_product(session)

        assert session.existing_product is None
        assert session.is_new_product is True
        assert session.sku is None
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_session_preview_new_product(self):
        """Test preview formatting for new product."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.name = "New Product"
        session.price = 1000.0
        session.quantity = 5
        session.is_new_product = True

        preview = service.format_session_preview(session)

        assert "Новый товар" in preview
        assert "New Product" in preview
        assert "1000" in preview
        assert "+5" in preview

    @pytest.mark.asyncio
    async def test_format_session_preview_with_weight(self):
        """Test preview formatting includes package weight."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.name = "Product with Weight"
        session.price = 500.0
        session.quantity = 10
        session.package_weight = 250
        session.is_new_product = True

        preview = service.format_session_preview(session)

        assert "⚖️ Вес: 250 г" in preview

    @pytest.mark.asyncio
    async def test_format_session_preview_existing_product(self, sample_product):
        """Test preview formatting for existing product."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.quantity = 5

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.set_existing_product(session, sample_product)

        preview = service.format_session_preview(session)

        assert "существующего" in preview
        assert sample_product.sku in preview
        # Stock preview: 10 -> 15
        assert "10" in preview
        assert "15" in preview


class TestIntakeServiceCompleteIntake:
    """Test cases for complete_intake method."""

    @pytest.mark.asyncio
    async def test_complete_new_product(self, mock_sheets_client, mock_settings):
        """Test completing intake for new product."""
        from app.models import IntakeSession, Product
        from app.services.intake_service import IntakeService

        # Setup mock
        mock_sheets_client.create_product = AsyncMock(return_value=Product(
            row_number=10,
            sku="PRD-NEW-0001",
            name="New Test",
            price=1000.0,
            stock=5,
            active=True,
        ))

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.name = "New Test"
        session.price = 1000.0
        session.quantity = 5
        session.is_new_product = True

        with patch("app.services.intake_service.sheets_client", mock_sheets_client):
            result = await service.complete_intake(session)

        assert result.success is True
        assert result.is_new is True
        assert result.product is not None

    @pytest.mark.asyncio
    async def test_complete_existing_product(self, mock_sheets_client, mock_settings, sample_product):
        """Test completing intake for existing product."""
        from app.models import IntakeSession, Product
        from app.services.intake_service import IntakeService

        mock_store = MagicMock()
        mock_store.save = AsyncMock()

        # Setup mock
        updated_product = Product(
            row_number=sample_product.row_number,
            sku=sample_product.sku,
            name=sample_product.name,
            price=sample_product.price,
            stock=sample_product.stock + 5,
            active=True,
        )
        mock_sheets_client.update_product_stock = AsyncMock(return_value=updated_product)

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.quantity = 5

        with patch("app.services.intake_service.intake_session_store", mock_store):
            await service.set_existing_product(session, sample_product)

        with patch("app.services.intake_service.sheets_client", mock_sheets_client):
            result = await service.complete_intake(session)

        assert result.success is True
        assert result.is_new is False
        assert result.product.stock == sample_product.stock + 5

    @pytest.mark.asyncio
    async def test_complete_missing_required_fields(self, mock_settings):
        """Test completing intake with missing fields fails."""
        from app.models import IntakeSession
        from app.services.intake_service import IntakeService

        service = IntakeService()
        session = IntakeSession(user_id=123456789)
        session.is_new_product = True
        # Missing name, price, quantity

        result = await service.complete_intake(session)

        assert result.success is False
        assert result.error is not None
        assert "обязательные поля" in result.error.lower()
