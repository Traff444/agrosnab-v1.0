"""Tests for intake flow and service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
