"""Tests for security module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock


class TestWhitelistMiddleware:
    """Test cases for WhitelistMiddleware."""

    @pytest.mark.asyncio
    async def test_allows_whitelisted_user(self, monkeypatch):
        """Test that whitelisted user is allowed."""
        from aiogram.types import Message
        from app.config import Settings

        settings = Settings(
            telegram_bot_token="test_token",
            owner_telegram_ids=[123456789],
            google_sheets_id="test_sheet_id",
            google_service_account_json_path="/tmp/test.json",
            drive_folder_id="test_folder_id",
        )
        monkeypatch.setattr("app.security.get_settings", lambda: settings)

        from app.security import WhitelistMiddleware

        middleware = WhitelistMiddleware()

        # Create mock message with spec to pass isinstance check
        message = MagicMock(spec=Message)
        message.from_user = MagicMock()
        message.from_user.id = 123456789  # In whitelist

        handler = AsyncMock(return_value="success")
        data = {}

        result = await middleware(handler, message, data)

        handler.assert_called_once()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_blocks_non_whitelisted_user(self, monkeypatch):
        """Test that non-whitelisted user is blocked."""
        from aiogram.types import Message
        from app.config import Settings

        settings = Settings(
            telegram_bot_token="test_token",
            owner_telegram_ids=[123456789],
            google_sheets_id="test_sheet_id",
            google_service_account_json_path="/tmp/test.json",
            drive_folder_id="test_folder_id",
        )
        monkeypatch.setattr("app.security.get_settings", lambda: settings)

        from app.security import WhitelistMiddleware

        middleware = WhitelistMiddleware()

        # Create mock message with spec to pass isinstance check
        message = MagicMock(spec=Message)
        message.from_user = MagicMock()
        message.from_user.id = 999999999  # Not in whitelist
        message.answer = AsyncMock()

        handler = AsyncMock()
        data = {}

        result = await middleware(handler, message, data)

        handler.assert_not_called()
        message.answer.assert_called_once()
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_callback_query(self, mock_settings):
        """Test handling of CallbackQuery."""
        from aiogram.types import CallbackQuery
        from app.security import WhitelistMiddleware

        middleware = WhitelistMiddleware()

        # Create mock callback with non-whitelisted user
        callback = MagicMock(spec=CallbackQuery)
        callback.from_user = MagicMock()
        callback.from_user.id = 999999999
        callback.answer = AsyncMock()

        handler = AsyncMock()
        data = {}

        result = await middleware(handler, callback, data)

        handler.assert_not_called()
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_user(self, mock_settings):
        """Test handling of event without user."""
        from app.security import WhitelistMiddleware

        middleware = WhitelistMiddleware()

        message = MagicMock()
        message.from_user = None

        handler = AsyncMock()
        data = {}

        result = await middleware(handler, message, data)

        handler.assert_not_called()
        assert result is None


class TestConfirmActionStore:
    """Test cases for ConfirmActionStore."""

    @pytest.mark.asyncio
    async def test_create_action(self, tmp_path):
        """Test creating a confirmation action."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)

        action_id = await store.create(
            action_type="test_action",
            payload={"key": "value"},
            owner_id=123456789,
            ttl_seconds=300,
        )

        assert action_id is not None
        assert len(action_id) > 0

    @pytest.mark.asyncio
    async def test_get_action(self, tmp_path):
        """Test retrieving a confirmation action."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)

        action_id = await store.create(
            action_type="test_action",
            payload={"key": "value"},
            owner_id=123456789,
            ttl_seconds=300,
        )

        action = await store.get(action_id)

        assert action is not None
        assert action["action_type"] == "test_action"
        assert action["payload"]["key"] == "value"
        assert action["owner_id"] == 123456789

    @pytest.mark.asyncio
    async def test_get_expired_action_returns_none(self, tmp_path):
        """Test that expired actions return None."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)

        # Create action with 0 TTL (immediately expired)
        action_id = await store.create(
            action_type="test_action",
            payload={},
            owner_id=123456789,
            ttl_seconds=0,
        )

        # Should return None for expired action
        action = await store.get(action_id)
        assert action is None

    @pytest.mark.asyncio
    async def test_delete_action(self, tmp_path):
        """Test deleting a confirmation action."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)

        action_id = await store.create(
            action_type="test_action",
            payload={},
            owner_id=123456789,
        )

        deleted = await store.delete(action_id)
        assert deleted is True

        # Should return None after deletion
        action = await store.get(action_id)
        assert action is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_action(self, tmp_path):
        """Test deleting nonexistent action."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)
        await store._ensure_initialized()

        deleted = await store.delete("nonexistent_id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, tmp_path):
        """Test cleanup of expired actions."""
        from app.security import ConfirmActionStore

        db_path = str(tmp_path / "test.db")
        store = ConfirmActionStore(db_path)

        # Create expired action
        await store.create(
            action_type="expired",
            payload={},
            owner_id=123456789,
            ttl_seconds=0,
        )

        # Create valid action
        await store.create(
            action_type="valid",
            payload={},
            owner_id=123456789,
            ttl_seconds=3600,
        )

        deleted_count = await store.cleanup_expired()

        # At least 1 expired action should be deleted
        assert deleted_count >= 1
