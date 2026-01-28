"""Security middleware and confirmation actions."""

import secrets
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from app.config import get_settings


class WhitelistMiddleware(BaseMiddleware):
    """Middleware to restrict bot access to whitelisted owners only."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Check if user is in whitelist before processing."""
        settings = get_settings()

        user_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return None

        if user_id not in settings.owner_telegram_ids:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещён. Этот бот только для владельца магазина.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещён", show_alert=True)
            return None

        return await handler(event, data)


class ConfirmActionStore:
    """SQLite-backed store for pending confirmation actions."""

    def __init__(self, db_path: str = "data/confirm_actions.db"):
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database and table exist."""
        if self._initialized:
            return

        import os

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS confirm_actions (
                    id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON confirm_actions(expires_at)
            """)
            await db.commit()

        self._initialized = True

    async def create(
        self,
        action_type: str,
        payload: dict[str, Any],
        owner_id: int,
        ttl_seconds: int = 300,
    ) -> str:
        """Create a new confirmation action with TTL."""
        import json

        await self._ensure_initialized()

        action_id = secrets.token_urlsafe(16)
        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl_seconds)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO confirm_actions (id, action_type, payload, owner_id, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    action_type,
                    json.dumps(payload),
                    owner_id,
                    expires_at.isoformat(),
                    now.isoformat(),
                ),
            )
            await db.commit()

        return action_id

    async def get(self, action_id: str) -> dict[str, Any] | None:
        """Get a confirmation action by ID if not expired."""
        import json

        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM confirm_actions WHERE id = ?",
                (action_id,),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                await self.delete(action_id)
                return None

            return {
                "id": row["id"],
                "action_type": row["action_type"],
                "payload": json.loads(row["payload"]),
                "owner_id": row["owner_id"],
                "expires_at": expires_at,
                "created_at": datetime.fromisoformat(row["created_at"]),
            }

    async def delete(self, action_id: str) -> bool:
        """Delete a confirmation action."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM confirm_actions WHERE id = ?",
                (action_id,),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def cleanup_expired(self) -> int:
        """Remove all expired actions. Returns count of deleted rows."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM confirm_actions WHERE expires_at < ?",
                (datetime.now().isoformat(),),
            )
            await db.commit()
            return cursor.rowcount


# Global store instance
confirm_store = ConfirmActionStore()
