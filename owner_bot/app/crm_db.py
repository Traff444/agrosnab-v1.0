"""CRM database access for Owner Bot.

Reads from the shared SQLite database used by Shop Bot.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import aiosqlite
import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# OpenAI timeout
OPENAI_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Use the same database path as Shop Bot
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = "/app/data/bot.sqlite3" if os.path.exists("/app/data") else str(_DATA_DIR / "bot.sqlite3")


async def get_user_messages(
    user_id: int,
    limit: int = 50,
    direction: str | None = None,
) -> list[dict]:
    """Get CRM messages for a user.

    Args:
        user_id: Telegram user ID
        limit: Maximum number of messages to return
        direction: Filter by direction ('in' or 'out'), or None for all

    Returns:
        List of message dicts with keys: id, direction, message_type, text, created_at
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if direction:
                cur = await db.execute(
                    """
                    SELECT id, direction, message_type, text, created_at
                    FROM crm_messages
                    WHERE user_id = ? AND direction = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, direction, limit),
                )
            else:
                cur = await db.execute(
                    """
                    SELECT id, direction, message_type, text, created_at
                    FROM crm_messages
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error("user_messages_fetch_failed", extra={"user_id": user_id, "error": str(e)})
        return []


async def get_user_messages_count(user_id: int) -> int:
    """Get total count of messages for a user."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM crm_messages WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0
    except Exception as e:
        logger.error("messages_count_failed", extra={"user_id": user_id, "error": str(e)})
        return 0


async def get_user_events(
    user_id: int,
    limit: int = 50,
    event_types: list[str] | None = None,
) -> list[dict]:
    """Get CRM events for a user.

    Args:
        user_id: Telegram user ID
        limit: Maximum number of events to return
        event_types: Filter by event types, or None for all

    Returns:
        List of event dicts with keys: id, event_type, payload_json, created_at
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if event_types:
                placeholders = ','.join('?' * len(event_types))
                cur = await db.execute(
                    f"""
                    SELECT id, event_type, payload_json, created_at
                    FROM crm_events
                    WHERE user_id = ? AND event_type IN ({placeholders})
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, *event_types, limit),
                )
            else:
                cur = await db.execute(
                    """
                    SELECT id, event_type, payload_json, created_at
                    FROM crm_events
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error("user_events_fetch_failed", extra={"user_id": user_id, "error": str(e)})
        return []


async def format_messages_for_display(user_id: int, limit: int = 20) -> str:
    """Format messages for display in Telegram.

    Returns messages in reverse chronological order, newest first.
    """
    messages = await get_user_messages(user_id, limit=limit)

    if not messages:
        return "Нет сообщений."

    # Reverse to show oldest first (chronological order)
    messages = list(reversed(messages))

    lines = []
    for msg in messages:
        direction = "👤" if msg['direction'] == 'in' else "🤖"
        text = msg['text'][:100] + "..." if len(msg['text']) > 100 else msg['text']
        ts = msg['created_at'][:16] if msg['created_at'] else ""
        lines.append(f"{direction} {ts}\n{text}")

    return "\n\n".join(lines)


SUMMARY_SYSTEM_PROMPT = """Ты — аналитик CRM для оптового магазина табачных изделий.

Тебе дана история переписки клиента с AI-продавцом. Создай краткую сводку для владельца магазина.

ФОРМАТ ОТВЕТА (строго на русском):
**Интерес:** что искал/спрашивал клиент
**Действия:** что добавил в корзину, заказывал
**Настроение:** позитивное/нейтральное/негативное/проблемное
**Рекомендация:** как работать с этим клиентом дальше

Ответ должен быть коротким (5-7 предложений максимум).
Если переписка пустая или неинформативная — напиши "Недостаточно данных для анализа."
"""


async def generate_ai_summary(
    user_id: int,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_messages: int = 30,
) -> str:
    """Generate AI summary of user's conversation history.

    Args:
        user_id: Telegram user ID
        api_key: OpenAI API key
        model: OpenAI model to use
        max_messages: Maximum number of messages to include

    Returns:
        AI-generated summary text
    """
    messages = await get_user_messages(user_id, limit=max_messages)

    if not messages:
        return "Нет сообщений для анализа."

    # Reverse to chronological order
    messages = list(reversed(messages))

    # Format conversation for AI
    conversation_lines = []
    for msg in messages:
        role = "Клиент" if msg['direction'] == 'in' else "AI-продавец"
        text = msg['text'][:500]  # Truncate long messages
        conversation_lines.append(f"{role}: {text}")

    conversation_text = "\n".join(conversation_lines)

    if len(conversation_text) < 20:
        return "Недостаточно данных для анализа."

    try:
        client = AsyncOpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Переписка клиента #{user_id}:\n\n{conversation_text}"},
            ],
            max_tokens=500,
            temperature=0.3,
        )

        return response.choices[0].message.content or "Не удалось сгенерировать сводку."

    except Exception as e:
        logger.error("ai_summary_failed", extra={"user_id": user_id, "error": str(e)})
        return f"Ошибка AI: {str(e)}"
