"""AI chat history storage."""

from __future__ import annotations

import aiosqlite

from .db import DB_PATH

MAX_HISTORY_MESSAGES = 20  # Store last 20 messages per user


async def add_chat_message(user_id: int, role: str, content: str) -> None:
    """Add a message to chat history. Role: 'user' or 'assistant' or 'system'."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history(user_id, role, content) VALUES(?, ?, ?)",
            (user_id, role, content),
        )
        # Remove old messages, keep only last N
        await db.execute(
            """
            DELETE FROM chat_history
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM chat_history WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            )
            """,
            (user_id, user_id, MAX_HISTORY_MESSAGES),
        )
        await db.commit()


async def get_chat_history(user_id: int) -> list[dict]:
    """Get chat history for user as list of {role, content} dicts."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]


async def clear_chat_history(user_id: int) -> None:
    """Clear chat history for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        await db.commit()


async def set_ai_mode(user_id: int, enabled: bool) -> None:
    """Set AI mode for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_mode(user_id, ai_mode) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET ai_mode=excluded.ai_mode",
            (user_id, 1 if enabled else 0),
        )
        await db.commit()


async def get_ai_mode(user_id: int) -> bool:
    """Check if AI mode is enabled for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT ai_mode FROM user_mode WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        return bool(row[0]) if row else False
