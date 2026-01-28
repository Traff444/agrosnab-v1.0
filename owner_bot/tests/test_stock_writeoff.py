"""Tests for stock writeoff functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.sheets import SheetsClient, StockOperationResult
from app.models import Product


@pytest.fixture
def mock_product():
    """Create a mock product for tests."""
    return Product(
        row_number=5,
        sku="PRD-20240101-ABCD",
        name="Test Product",
        price=500.0,
        stock=10,
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


class TestApplyWriteoff:
    """Tests for apply_writeoff method."""

    @pytest.mark.asyncio
    async def test_successful_writeoff_decreases_stock(
        self, sheets_client_with_mocks, mock_product
    ):
        """Successful writeoff should decrease stock and return ok=True."""
        client = sheets_client_with_mocks

        # Mock get_product_by_row
        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            # Mock append_log_entry
            with patch.object(
                client, "append_log_entry", new_callable=AsyncMock
            ) as mock_append:
                mock_append.return_value = True

                # Mock update_product_stock
                with patch.object(
                    client, "update_product_stock", new_callable=AsyncMock
                ) as mock_update:
                    mock_update.return_value = Product(
                        **{**mock_product.__dict__, "stock": 7}
                    )

                    # Mock _increment_total_column
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        result = await client.apply_writeoff(
                            row_number=5,
                            qty=3,
                            reason="порча",
                            actor_id=123456,
                            actor_username="testuser",
                        )

        assert result.ok is True
        assert result.stock_before == 10
        assert result.stock_after == 7
        assert result.error is None

    @pytest.mark.asyncio
    async def test_writeoff_logs_to_spisanie_sheet(
        self, sheets_client_with_mocks, mock_product
    ):
        """Writeoff should log to 'Списание' sheet with correct fields."""
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
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        await client.apply_writeoff(
                            row_number=5,
                            qty=3,
                            reason="подарок",
                            actor_id=123456,
                            actor_username="testuser",
                        )

            # Verify append_log_entry was called with correct params
            mock_append.assert_called_once()
            call_kwargs = mock_append.call_args.kwargs
            assert call_kwargs["sheet_name"] == "Списание"
            assert call_kwargs["sku"] == "PRD-20240101-ABCD"
            assert call_kwargs["name"] == "Test Product"
            assert call_kwargs["qty"] == 3
            assert call_kwargs["stock_before"] == 10
            assert call_kwargs["stock_after"] == 7
            assert call_kwargs["reason"] == "подарок"
            assert call_kwargs["source"] == "owner_manual"
            assert call_kwargs["actor_id"] == 123456
            assert call_kwargs["actor_username"] == "testuser"

    @pytest.mark.asyncio
    async def test_writeoff_rejects_zero_qty(
        self, sheets_client_with_mocks, mock_product
    ):
        """Writeoff should reject qty <= 0."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            result = await client.apply_writeoff(
                row_number=5,
                qty=0,
                reason="порча",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "больше 0" in result.error

    @pytest.mark.asyncio
    async def test_writeoff_rejects_negative_qty(
        self, sheets_client_with_mocks, mock_product
    ):
        """Writeoff should reject negative qty."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            result = await client.apply_writeoff(
                row_number=5,
                qty=-5,
                reason="порча",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "больше 0" in result.error

    @pytest.mark.asyncio
    async def test_writeoff_rejects_qty_exceeding_stock(
        self, sheets_client_with_mocks, mock_product
    ):
        """Writeoff should reject qty > current stock."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            result = await client.apply_writeoff(
                row_number=5,
                qty=15,  # More than stock of 10
                reason="порча",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "Недостаточно" in result.error

    @pytest.mark.asyncio
    async def test_writeoff_deduplication_by_operation_id(
        self, sheets_client_with_mocks, mock_product
    ):
        """Duplicate operation_id should be detected and skipped."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_product

            # Mock _check_operation_exists to return True (duplicate found)
            with patch.object(
                client, "_check_operation_exists", new_callable=AsyncMock
            ) as mock_check:
                mock_check.return_value = True

                with patch.object(
                    client, "ensure_log_columns", new_callable=AsyncMock
                ) as mock_ensure:
                    mock_ensure.return_value = {"date": 0, "operation_id": 1}

                    with patch.object(
                        client, "update_product_stock", new_callable=AsyncMock
                    ) as mock_update:
                        mock_update.return_value = Product(
                            **{**mock_product.__dict__, "stock": 7}
                        )

                        with patch.object(
                            client, "_increment_total_column", new_callable=AsyncMock
                        ):
                            result = await client.apply_writeoff(
                                row_number=5,
                                qty=3,
                                reason="порча",
                                actor_id=123456,
                                actor_username="testuser",
                                operation_id="existing_op_id",
                            )

        # Should still succeed (dedup found existing entry)
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_writeoff_returns_error_when_product_not_found(
        self, sheets_client_with_mocks
    ):
        """Writeoff should return error if product not found."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "get_product_by_row", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            result = await client.apply_writeoff(
                row_number=5,
                qty=3,
                reason="порча",
                actor_id=123456,
                actor_username="testuser",
            )

        assert result.ok is False
        assert "не найден" in result.error

    @pytest.mark.asyncio
    async def test_writeoff_updates_spisano_vsego_column(
        self, sheets_client_with_mocks, mock_product
    ):
        """Writeoff should update Списано_всего if column exists."""
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
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ) as mock_increment:
                        await client.apply_writeoff(
                            row_number=5,
                            qty=3,
                            reason="порча",
                            actor_id=123456,
                            actor_username="testuser",
                        )

                        # Verify _increment_total_column was called
                        mock_increment.assert_called_once_with(5, "Списано_всего", 3)

    @pytest.mark.asyncio
    async def test_writeoff_preserves_operation_id_for_retry(
        self, sheets_client_with_mocks, mock_product
    ):
        """Operation ID should be preserved in result for retry scenarios."""
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
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        # Test with provided operation_id
                        result = await client.apply_writeoff(
                            row_number=5,
                            qty=3,
                            reason="порча",
                            actor_id=123456,
                            actor_username="testuser",
                            operation_id="my_custom_op_id",
                        )

        assert result.operation_id == "my_custom_op_id"

    @pytest.mark.asyncio
    async def test_writeoff_generates_operation_id_if_not_provided(
        self, sheets_client_with_mocks, mock_product
    ):
        """Operation ID should be generated if not provided."""
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
                ):
                    with patch.object(
                        client, "_increment_total_column", new_callable=AsyncMock
                    ):
                        result = await client.apply_writeoff(
                            row_number=5,
                            qty=3,
                            reason="порча",
                            actor_id=123456,
                            actor_username="testuser",
                        )

        # Should have generated an operation_id
        assert result.operation_id is not None
        assert len(result.operation_id) == 16  # hex(8 bytes) = 16 chars


class TestStockOperationResult:
    """Tests for StockOperationResult dataclass."""

    def test_result_fields(self):
        """Test StockOperationResult has all required fields."""
        result = StockOperationResult(
            ok=True,
            stock_before=10,
            stock_after=7,
            operation_id="test_op",
            error=None,
        )

        assert result.ok is True
        assert result.stock_before == 10
        assert result.stock_after == 7
        assert result.operation_id == "test_op"
        assert result.error is None

    def test_result_with_error(self):
        """Test StockOperationResult with error."""
        result = StockOperationResult(
            ok=False,
            stock_before=10,
            stock_after=10,
            operation_id="test_op",
            error="Something went wrong",
        )

        assert result.ok is False
        assert result.error == "Something went wrong"
