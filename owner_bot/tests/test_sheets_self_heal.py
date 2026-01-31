"""Tests for sheets self-heal functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.sheets import LOG_COLUMNS, SheetsClient


@pytest.fixture
def sheets_client_with_mocks(mock_settings):
    """Create a SheetsClient with mocked service."""
    client = SheetsClient()
    client._col_map = {"SKU": 0}
    client._service = MagicMock()
    return client


class TestEnsureLogColumns:
    """Tests for ensure_log_columns method."""

    @pytest.mark.asyncio
    async def test_adds_missing_columns_to_end(self, sheets_client_with_mocks):
        """Missing columns should be added to the end of header row."""
        client = sheets_client_with_mocks

        # Mock _ensure_sheet_exists
        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock spreadsheets().values().get() to return partial headers
            mock_get = MagicMock()
            mock_get.execute.return_value = {
                "values": [["date", "operation_id", "sku"]]  # Missing other columns
            }
            client.service.spreadsheets().values().get.return_value = mock_get

            # Mock spreadsheets().values().update()
            mock_update = MagicMock()
            mock_update.execute.return_value = {}
            client.service.spreadsheets().values().update.return_value = mock_update

            # Call ensure_log_columns
            result = await client.ensure_log_columns("Списание")

            # Verify update was called to add missing columns
            client.service.spreadsheets().values().update.assert_called_once()
            call_args = client.service.spreadsheets().values().update.call_args

            # Missing columns should be: name, qty, stock_before, stock_after, reason, source, actor_id, actor_username, note
            expected_missing = [c for c in LOG_COLUMNS if c not in ["date", "operation_id", "sku"]]
            assert call_args.kwargs["body"]["values"][0] == expected_missing

        # Result should include all columns
        assert "date" in result
        assert "operation_id" in result
        assert "sku" in result
        assert "name" in result
        assert "qty" in result

    @pytest.mark.asyncio
    async def test_preserves_existing_columns(self, sheets_client_with_mocks):
        """Existing columns should be preserved in their positions."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock get() to return all columns already present
            mock_get = MagicMock()
            mock_get.execute.return_value = {"values": [LOG_COLUMNS]}
            client.service.spreadsheets().values().get.return_value = mock_get

            # Call ensure_log_columns
            result = await client.ensure_log_columns("Списание")

            # Verify update was NOT called (no missing columns)
            client.service.spreadsheets().values().update.assert_not_called()

        # All columns should be in result with correct indices
        for idx, col in enumerate(LOG_COLUMNS):
            assert result[col] == idx

    @pytest.mark.asyncio
    async def test_creates_sheet_if_missing(self, sheets_client_with_mocks):
        """Sheet should be created if it doesn't exist."""
        client = sheets_client_with_mocks

        # Mock _ensure_sheet_exists to track if it's called
        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock get() to return empty (no headers yet)
            mock_get = MagicMock()
            mock_get.execute.return_value = {"values": []}
            client.service.spreadsheets().values().get.return_value = mock_get

            # Mock update()
            mock_update = MagicMock()
            mock_update.execute.return_value = {}
            client.service.spreadsheets().values().update.return_value = mock_update

            await client.ensure_log_columns("Списание")

            # Verify _ensure_sheet_exists was called
            mock_ensure_sheet.assert_called_once_with("Списание")

    @pytest.mark.asyncio
    async def test_initializes_empty_sheet_with_all_columns(
        self, sheets_client_with_mocks
    ):
        """Empty sheet should be initialized with all columns."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock get() to return empty (new sheet)
            mock_get = MagicMock()
            mock_get.execute.return_value = {}  # No values at all
            client.service.spreadsheets().values().get.return_value = mock_get

            # Mock update()
            mock_update = MagicMock()
            mock_update.execute.return_value = {}
            client.service.spreadsheets().values().update.return_value = mock_update

            await client.ensure_log_columns("Списание")

            # Verify update was called with all columns
            update_calls = client.service.spreadsheets().values().update.call_args_list

            # Should write all LOG_COLUMNS to A1
            found_full_init = any(
                call.kwargs.get("body", {}).get("values", [[]])[0] == LOG_COLUMNS
                for call in update_calls
            )
            assert found_full_init

    @pytest.mark.asyncio
    async def test_caches_column_mapping(self, sheets_client_with_mocks):
        """Column mapping should be cached after first call."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock get()
            mock_get = MagicMock()
            mock_get.execute.return_value = {"values": [LOG_COLUMNS]}
            client.service.spreadsheets().values().get.return_value = mock_get

            # First call
            result1 = await client.ensure_log_columns("Списание")

            # Second call
            result2 = await client.ensure_log_columns("Списание")

            # get() should only be called once (cached)
            assert client.service.spreadsheets().values().get.call_count == 1

            # Results should be the same
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_clear_cache_allows_refresh(self, sheets_client_with_mocks):
        """Clearing cache should allow fresh column read."""
        client = sheets_client_with_mocks

        with patch.object(
            client, "_ensure_sheet_exists", new_callable=AsyncMock
        ) as mock_ensure_sheet:
            mock_ensure_sheet.return_value = True

            # Mock get()
            mock_get = MagicMock()
            mock_get.execute.return_value = {"values": [LOG_COLUMNS]}
            client.service.spreadsheets().values().get.return_value = mock_get

            # First call
            await client.ensure_log_columns("Списание")

            # Clear cache
            client.clear_log_column_cache("Списание")

            # Second call after cache clear
            await client.ensure_log_columns("Списание")

            # get() should be called twice now
            assert client.service.spreadsheets().values().get.call_count == 2


class TestEnsureSheetExists:
    """Tests for _ensure_sheet_exists method."""

    @pytest.mark.asyncio
    async def test_returns_true_if_sheet_exists(self, sheets_client_with_mocks):
        """Should return True if sheet already exists."""
        client = sheets_client_with_mocks

        # Mock spreadsheets().get() to return sheet list including target
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "sheets": [
                {"properties": {"title": "Склад"}},
                {"properties": {"title": "Списание"}},
            ]
        }
        client.service.spreadsheets().get.return_value = mock_get

        result = await client._ensure_sheet_exists("Списание")

        assert result is True
        # batchUpdate should NOT be called (sheet exists)
        client.service.spreadsheets().batchUpdate.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_sheet_if_not_exists(self, sheets_client_with_mocks):
        """Should create sheet if it doesn't exist."""
        client = sheets_client_with_mocks

        # Mock spreadsheets().get() to return sheet list without target
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "sheets": [{"properties": {"title": "Склад"}}]
        }
        client.service.spreadsheets().get.return_value = mock_get

        # Mock batchUpdate()
        mock_batch = MagicMock()
        mock_batch.execute.return_value = {}
        client.service.spreadsheets().batchUpdate.return_value = mock_batch

        result = await client._ensure_sheet_exists("Списание")

        assert result is True
        # batchUpdate should be called to create sheet
        client.service.spreadsheets().batchUpdate.assert_called_once()

        # Verify addSheet request
        call_kwargs = client.service.spreadsheets().batchUpdate.call_args.kwargs
        requests = call_kwargs["body"]["requests"]
        assert len(requests) == 1
        assert "addSheet" in requests[0]
        assert requests[0]["addSheet"]["properties"]["title"] == "Списание"


class TestCheckOperationExists:
    """Tests for _check_operation_exists method."""

    @pytest.mark.asyncio
    async def test_returns_true_if_operation_found(self, sheets_client_with_mocks):
        """Should return True if operation_id exists in recent rows."""
        client = sheets_client_with_mocks

        # Mock get() to return rows with operation_id
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "values": [
                ["2024-01-01", "abc123", "SKU1"],
                ["2024-01-02", "def456", "SKU2"],
                ["2024-01-03", "target_op", "SKU3"],
            ]
        }
        client.service.spreadsheets().values().get.return_value = mock_get

        result = await client._check_operation_exists("Списание", "target_op")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_if_operation_not_found(
        self, sheets_client_with_mocks
    ):
        """Should return False if operation_id not in recent rows."""
        client = sheets_client_with_mocks

        # Mock get() to return rows without target operation_id
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "values": [
                ["2024-01-01", "abc123", "SKU1"],
                ["2024-01-02", "def456", "SKU2"],
            ]
        }
        client.service.spreadsheets().values().get.return_value = mock_get

        result = await client._check_operation_exists("Списание", "not_found_op")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_empty_sheet(self, sheets_client_with_mocks):
        """Should return False if sheet is empty."""
        client = sheets_client_with_mocks

        # Mock get() to return empty
        mock_get = MagicMock()
        mock_get.execute.return_value = {"values": []}
        client.service.spreadsheets().values().get.return_value = mock_get

        result = await client._check_operation_exists("Списание", "any_op")

        assert result is False
