"""Database configuration and initialization."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

# Use relative path for local development, absolute for Docker
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
if os.path.exists("/app/data"):
    DB_PATH = "/app/data/bot.sqlite3"
else:
    _DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = str(_DATA_DIR / "bot.sqlite3")


async def init_db() -> None:
    """Initialize all database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Cart items
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS cart_items (
                user_id INTEGER NOT NULL,
                sku TEXT NOT NULL,
                qty INTEGER NOT NULL,
                PRIMARY KEY (user_id, sku)
            );
            """
        )

        # User AI mode
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_mode (
                user_id INTEGER PRIMARY KEY,
                ai_mode INTEGER NOT NULL DEFAULT 0
            );
            """
        )

        # Chat history for AI
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Checkout sessions (idempotency)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS checkout_sessions (
                user_id INTEGER NOT NULL,
                cart_hash TEXT NOT NULL,
                order_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, cart_hash)
            );
            """
        )

        # Indexes for chat history
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id, created_at)"
        )

        # CRM events table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_crm_events_user ON crm_events(user_id, created_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_crm_events_type ON crm_events(event_type, created_at)"
        )

        # CRM messages table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                direction TEXT NOT NULL,
                message_type TEXT NOT NULL DEFAULT 'text',
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_crm_messages_user ON crm_messages(user_id, created_at)"
        )

        await db.commit()
