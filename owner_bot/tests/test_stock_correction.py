"""Tests for stock correction functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Product
from app.sheets import SheetsClient


@pytest.fixture
def mock_product():
    """Create a mock product for tests."""
    return Product(
        row_number=5,
        sku="PRD-20240101-ABCD",
        name="Test Product",
        price=500.0,
        stock=42,
        photo_url="https://example.com/photo.jpg",
        description="Test description",
        tags="test",
        active=True,
    )


@pytest.fixture
def sheets_client_with_mocks(mock_settings):
    """Create a SheetsClient with mocked service."""
    client = SheetsClient()
    client._col_map = {
        "SKU": 0,
        "Наименование": 1,
        "Цена_руб": 2,
        "Остаток_расчет": 3,
        "Фото_URL": 4,
        "Активен": 5,
        "Списано_всего": 6,
        "Внесено_всего": 7,
    }
    client._service = MagicMock()
    return client


class TestApplyCorrection:
    """Tests for apply_correction method."""

    @pytest.mark.asyncio
    async def test_correction_down_logs_to_spisanie(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction down (delta < 0) should log to 'Списание' sheet."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product  # stock = 42

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ), patch.object(
                    client, "_increment_total_column", new_callable=AsyncMock
                ):
                    result = await client.apply_correction(
                        row_number=5,
                        new_stock=37,  # delta = -5
                        reason="инвентаризация",
                        actor_id=123456,
                        actor_username="testuser",
                    )

            # Verify log entry went to Списание
            mock_append.assert_called_once()
            call_kwargs = mock_append.call_args.kwargs
            assert call_kwargs["sheet_name"] == "Списание"
            assert call_kwargs["qty"] == 5  # abs(delta)
            assert call_kwargs["stock_before"] == 42
            assert call_kwargs["stock_after"] == 37
            assert call_kwargs["reason"] == "correction:инвентаризация"
            assert call_kwargs["source"] == "owner_correction"

        assert result.ok is True
        assert result.stock_before == 42
        assert result.stock_after == 37

    @pytest.mark.asyncio
    async def test_correction_up_logs_to_vnesenie(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction up (delta > 0) should log to 'Внесение' sheet."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product  # stock = 42

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ), patch.object(
                    client, "_increment_total_column", new_callable=AsyncMock
                ):
                    result = await client.apply_correction(
                        row_number=5,
                        new_stock=50,  # delta = +8
                        reason="пересорт",
                        actor_id=123456,
                        actor_username="testuser",
                    )

            # Verify log entry went to Внесение
            mock_append.assert_called_once()
            call_kwargs = mock_append.call_args.kwargs
            assert call_kwargs["sheet_name"] == "Внесение"
            assert call_kwargs["qty"] == 8  # delta
            assert call_kwargs["stock_before"] == 42
            assert call_kwargs["stock_after"] == 50
            assert call_kwargs["reason"] == "correction:пересорт"
            assert call_kwargs["source"] == "owner_correction"

        assert result.ok is True
        assert result.stock_before == 42
        assert result.stock_after == 50

    @pytest.mark.asyncio
    async def test_correction_zero_delta_no_log(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction with delta == 0 should not write to log."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product  # stock = 42

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                result = await client.apply_correction(
                    row_number=5,
                    new_stock=42,  # delta = 0
                    reason="инвентаризация",
                    actor_id=123456,
                    actor_username="testuser",
                )

            # Verify no log entry was made
            mock_append.assert_not_called()

        assert result.ok is True
        assert result.stock_before == 42
        assert result.stock_after == 42

    @pytest.mark.asyncio
    async def test_correction_rejects_negative_stock(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction should reject negative new_stock value."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            result = await client.apply_correction(
                row_number=5,
                new_stock=-5,  # Invalid
                reason="инвентаризация",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "отрицательным" in result.error

    @pytest.mark.asyncio
    async def test_correction_returns_error_when_product_not_found(
        self, sheets_client_with_mocks
    ):
        """Correction should return error if product not found."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await client.apply_correction(
                row_number=5,
                new_stock=37,
                reason="инвентаризация",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_correction_updates_spisano_vsego_for_decrease(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction down should update Списано_всего."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ), patch.object(
                    client, "_increment_total_column", new_callable=AsyncMock
                ) as mock_increment:
                    await client.apply_correction(
                        row_number=5,
                        new_stock=37,  # delta = -5
                        reason="инвентаризация",
                        actor_id=123456,
                        actor_username="testuser",
                    )

                    mock_increment.assert_called_once_with(5, "Списано_всего", 5)

    @pytest.mark.asyncio
    async def test_correction_updates_vneseno_vsego_for_increase(
        self, sheets_client_with_mocks, mock_product
    ):
        """Correction up should update Внесено_всего."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ), patch.object(
                    client, "_increment_total_column", new_callable=AsyncMock
                ) as mock_increment:
                    await client.apply_correction(
                        row_number=5,
                        new_stock=50,  # delta = +8
                        reason="пересорт",
                        actor_id=123456,
                        actor_username="testuser",
                    )

                    mock_increment.assert_called_once_with(5, "Внесено_всего", 8)

    @pytest.mark.asyncio
    async def test_correction_preserves_operation_id(
        self, sheets_client_with_mocks, mock_product
    ):
        """Operation ID should be preserved in result."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ), patch.object(
                    client, "_increment_total_column", new_callable=AsyncMock
                ):
                    result = await client.apply_correction(
                        row_number=5,
                        new_stock=37,
                        reason="инвентаризация",
                        actor_id=123456,
                        actor_username="testuser",
                        operation_id="my_op_id",
                    )

        assert result.operation_id == "my_op_id"
