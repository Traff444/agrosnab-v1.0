"""Tests for stock archive functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.sheets import SheetsClient
from app.models import Product


@pytest.fixture
def mock_product_with_stock():
    """Create a mock product with stock."""
    return Product(
        row_number=5,
        sku="PRD-20240101-ABCD",
        name="Test Product",
        price=500.0,
        stock=15,  # Has stock
        photo_url="https://example.com/photo.jpg",
        description="Test description",
        tags="test",
        active=True,
    )


@pytest.fixture
def mock_product_zero_stock():
    """Create a mock product with zero stock."""
    return Product(
        row_number=5,
        sku="PRD-20240101-ABCD",
        name="Test Product",
        price=500.0,
        stock=0,  # Zero stock
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
    }
    client._service = MagicMock()
    return client


class TestApplyArchiveZeroOut:
    """Tests for apply_archive_zero_out method."""

    @pytest.mark.asyncio
    async def test_archive_with_stock_logs_writeoff(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Archive with stock > 0 should log to 'Списание' with reason archive:zero_out."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_with_stock

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        with patch.object(
                            client, "update_product_active", new_callable=AsyncMock
                        ):
                            result = await client.apply_archive_zero_out(
                                row_number=5,
                                actor_id=123456,
                                actor_username="testuser",
                            )

            # Verify log entry went to Списание
            mock_append.assert_called_once()
            call_kwargs = mock_append.call_args.kwargs
            assert call_kwargs["sheet_name"] == "Списание"
            assert call_kwargs["qty"] == 15  # All stock
            assert call_kwargs["stock_before"] == 15
            assert call_kwargs["stock_after"] == 0
            assert call_kwargs["reason"] == "archive:zero_out"
            assert call_kwargs["source"] == "owner_manual"

        assert result.ok is True
        assert result.stock_before == 15
        assert result.stock_after == 0

    @pytest.mark.asyncio
    async def test_archive_with_stock_deactivates_product(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Archive should deactivate product after zeroing stock."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_with_stock

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        with patch.object(
                            client, "update_product_active", new_callable=AsyncMock
                        ) as mock_deactivate:
                            await client.apply_archive_zero_out(
                                row_number=5,
                                actor_id=123456,
                                actor_username="testuser",
                            )

                            # Verify product was deactivated
                            mock_deactivate.assert_called_once()
                            call_kwargs = mock_deactivate.call_args.kwargs
                            assert call_kwargs["active"] is False

    @pytest.mark.asyncio
    async def test_archive_zero_stock_no_log(
        self, sheets_client_with_mocks, mock_product_zero_stock
    ):
        """Archive with stock == 0 should not log writeoff."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_zero_stock

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                with patch.object(
                    client, "update_product_active", new_callable=AsyncMock
                ):
                    result = await client.apply_archive_zero_out(
                        row_number=5,
                        actor_id=123456,
                        actor_username="testuser",
                    )

            # Verify no log entry was made
            mock_append.assert_not_called()

        assert result.ok is True
        assert result.stock_before == 0
        assert result.stock_after == 0

    @pytest.mark.asyncio
    async def test_archive_zero_stock_still_deactivates(
        self, sheets_client_with_mocks, mock_product_zero_stock
    ):
        """Archive with stock == 0 should still deactivate product."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_zero_stock

            with patch.object(
                client, "update_product_active", new_callable=AsyncMock
            ) as mock_deactivate:
                await client.apply_archive_zero_out(
                    row_number=5,
                    actor_id=123456,
                    actor_username="testuser",
                )

                # Verify product was deactivated
                mock_deactivate.assert_called_once()
                call_kwargs = mock_deactivate.call_args.kwargs
                assert call_kwargs["active"] is False

    @pytest.mark.asyncio
    async def test_archive_returns_error_when_product_not_found(
        self, sheets_client_with_mocks
    ):
        """Archive should return error if product not found."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await client.apply_archive_zero_out(
                row_number=5,
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_archive_updates_spisano_vsego(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Archive with stock should update Списано_всего."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_with_stock

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ) as mock_increment:
                        with patch.object(
                            client, "update_product_active", new_callable=AsyncMock
                        ):
                            await client.apply_archive_zero_out(
                                row_number=5,
                                actor_id=123456,
                                actor_username="testuser",
                            )

                            # Verify increment was called with full stock amount
                            mock_increment.assert_called_once_with(
                                5, "Списано_всего", 15
                            )

    @pytest.mark.asyncio
    async def test_archive_fails_if_log_fails(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Archive should fail if log entry fails."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product_with_stock

            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = False  # Log failed

                result = await client.apply_archive_zero_out(
                    row_number=5,
                    actor_id=123456,
                    actor_username="testuser",
                )

        assert result.ok is False
        assert "журнал" in result.error


class TestSimpleArchive:
    """Tests for simple archive (deactivate only, no stock change).

    Note: Simple archive is handled at the handler level, not in sheets.py.
    These tests verify the expected behavior through update_product_active.
    """

    @pytest.mark.asyncio
    async def test_simple_archive_does_not_change_stock(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Simple archive should only deactivate, not change stock."""
        client = sheets_client_with_mocks

        # Simulate simple archive by calling update_product_active directly
        with patch.object(
            client.service.spreadsheets().values(), "batchUpdate"
        ) as mock_batch:
            mock_batch.return_value.execute.return_value = {}

            # This simulates what happens in the handler for simple archive
            result = await client.update_product_active(
                product=mock_product_with_stock,
                active=False,
                updated_by="tg:testuser",
            )

        # Stock should remain unchanged
        assert result.stock == mock_product_with_stock.stock
        assert result.active is False

    @pytest.mark.asyncio
    async def test_simple_archive_does_not_log(
        self, sheets_client_with_mocks, mock_product_with_stock
    ):
        """Simple archive should not create any log entries."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "append_log_entry", new_callable=AsyncMock
        ) as mock_append:
            with patch.object(
                client.service.spreadsheets().values(), "batchUpdate"
            ) as mock_batch:
                mock_batch.return_value.execute.return_value = {}

                # Simple archive only calls update_product_active
                await client.update_product_active(
                    product=mock_product_with_stock,
                    active=False,
                    updated_by="tg:testuser",
                )

            # No log entry should be made
            mock_append.assert_not_called()
