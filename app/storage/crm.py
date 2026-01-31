"""CRM events and messages storage."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Literal, TypedDict

import aiosqlite

from .db import DB_PATH

logger = logging.getLogger(__name__)

# Type definitions
CrmStage = Literal["new", "engaged", "cart", "checkout", "customer", "repeat"]
EventType = Literal[
    "start", "catalog_view", "product_view", "search",
    "add_to_cart", "checkout_started", "order_created"
]
MessageDirection = Literal["in", "out"]
MessageType = Literal["text", "photo", "voice", "command"]


class CrmEvent(TypedDict):
    """CRM event structure."""

    id: int
    event_type: str
    payload: dict[str, Any] | None
    created_at: str


class CrmMessage(TypedDict):
    """CRM message structure."""

    id: int
    direction: MessageDirection
    message_type: MessageType
    text: str
    created_at: str


class DailyStats(TypedDict):
    """Daily CRM statistics structure."""

    date: str
    visitors: int
    engaged: int
    cart: int
    checkout: int
    orders: int
    orders_total: int

# CRM Stage priorities (higher = further in funnel)
STAGE_PRIORITY = {
    "new": 1,
    "engaged": 2,
    "cart": 3,
    "checkout": 4,
    "customer": 5,
    "repeat": 6,
}

# Event to stage mapping
EVENT_TO_STAGE = {
    "start": "new",
    "catalog_view": "engaged",
    "product_view": "engaged",
    "search": "engaged",
    "add_to_cart": "cart",
    "checkout_started": "checkout",
    "order_created": "customer",  # or 'repeat' if orders_count >= 2
}

MAX_CRM_MESSAGES = 100  # Store last 100 messages per user


# ---------------------------------------------------------------------------
# CRM Events
# ---------------------------------------------------------------------------


async def log_crm_event(
    user_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """Log a CRM event to SQLite. Returns the event_id."""
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO crm_events(user_id, event_type, payload_json) VALUES(?, ?, ?)",
            (user_id, event_type, payload_json),
        )
        event_id = cursor.lastrowid
        await db.commit()
        logger.debug(
            "CRM event logged: user=%s, type=%s, id=%s", user_id, event_type, event_id
        )
        return event_id


async def get_user_events(
    user_id: int,
    limit: int = 50,
    event_types: list[str] | None = None,
) -> list[CrmEvent]:
    """Get CRM events for a user. Returns list of CrmEvent dicts."""
    async with aiosqlite.connect(DB_PATH) as db:
        if event_types:
            placeholders = ",".join("?" * len(event_types))
            query = f"""
                SELECT id, event_type, payload_json, created_at
                FROM crm_events
                WHERE user_id = ? AND event_type IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [user_id, *event_types, limit]
        else:
            query = """
                SELECT id, event_type, payload_json, created_at
                FROM crm_events
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [user_id, limit]

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        events = []
        for row in rows:
            payload = json.loads(row[2]) if row[2] else None
            events.append(
                {
                    "id": row[0],
                    "event_type": row[1],
                    "payload": payload,
                    "created_at": row[3],
                }
            )
        return events


async def get_user_stage(user_id: int) -> CrmStage | None:
    """Calculate current CRM stage for user based on their events."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT event_type FROM crm_events WHERE user_id = ?",
            (user_id,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return None

        event_types = [row[0] for row in rows]

        # Find highest stage based on events
        max_priority = 0
        max_stage = None

        for event_type in event_types:
            stage = EVENT_TO_STAGE.get(event_type)
            if stage:
                priority = STAGE_PRIORITY.get(stage, 0)
                if priority > max_priority:
                    max_priority = priority
                    max_stage = stage

        return max_stage


async def get_user_orders_count(user_id: int) -> int:
    """Count order_created events for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM crm_events WHERE user_id = ? AND event_type = 'order_created'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_daily_stats(target_date: str | date | None = None) -> DailyStats:
    """Get CRM statistics for a specific day."""
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        stats = {
            "date": target_date,
            "visitors": 0,
            "engaged": 0,
            "cart": 0,
            "checkout": 0,
            "orders": 0,
            "orders_total": 0,
        }

        # Visitors (unique users with 'start' event)
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM crm_events
            WHERE event_type = 'start' AND DATE(created_at) = ?
            """,
            (target_date,),
        )
        row = await cursor.fetchone()
        stats["visitors"] = row[0] if row else 0

        # Engaged (unique users who viewed catalog/product/search)
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM crm_events
            WHERE event_type IN ('catalog_view', 'product_view', 'search')
            AND DATE(created_at) = ?
            """,
            (target_date,),
        )
        row = await cursor.fetchone()
        stats["engaged"] = row[0] if row else 0

        # Cart (unique users who added to cart)
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM crm_events
            WHERE event_type = 'add_to_cart' AND DATE(created_at) = ?
            """,
            (target_date,),
        )
        row = await cursor.fetchone()
        stats["cart"] = row[0] if row else 0

        # Checkout started
        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM crm_events
            WHERE event_type = 'checkout_started' AND DATE(created_at) = ?
            """,
            (target_date,),
        )
        row = await cursor.fetchone()
        stats["checkout"] = row[0] if row else 0

        # Orders created and sum totals
        cursor = await db.execute(
            """
            SELECT payload_json
            FROM crm_events
            WHERE event_type = 'order_created' AND DATE(created_at) = ?
            """,
            (target_date,),
        )
        order_rows = await cursor.fetchall()
        stats["orders"] = len(order_rows)

        total = 0
        for row in order_rows:
            if row[0]:
                try:
                    payload = json.loads(row[0])
                    total += payload.get("total", 0)
                except (json.JSONDecodeError, TypeError):
                    pass
        stats["orders_total"] = total

        return stats


async def get_first_seen(user_id: int) -> str | None:
    """Get timestamp of first event for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT MIN(created_at) FROM crm_events WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


async def get_last_seen(user_id: int) -> str | None:
    """Get timestamp of last event for user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT MAX(created_at) FROM crm_events WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None


def compute_stage(current_stage: CrmStage | None, new_stage: CrmStage) -> CrmStage:
    """Compute resulting stage. Stage only goes UP, never down."""
    if current_stage is None:
        return new_stage

    current_priority = STAGE_PRIORITY.get(current_stage, 0)
    new_priority = STAGE_PRIORITY.get(new_stage, 0)

    if new_priority > current_priority:
        return new_stage
    return current_stage


# ---------------------------------------------------------------------------
# CRM Messages
# ---------------------------------------------------------------------------


async def log_crm_message(
    user_id: int,
    direction: MessageDirection,
    text: str,
    message_type: MessageType = "text",
) -> int:
    """Log a message to CRM history. Returns the message_id."""
    # Truncate very long messages
    if len(text) > 2000:
        text = text[:2000] + "..."

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO crm_messages(user_id, direction, message_type, text)
            VALUES(?, ?, ?, ?)
            """,
            (user_id, direction, message_type, text),
        )
        message_id = cursor.lastrowid

        # Cleanup old messages, keep only last N
        await db.execute(
            """
            DELETE FROM crm_messages
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM crm_messages WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            )
            """,
            (user_id, user_id, MAX_CRM_MESSAGES),
        )
        await db.commit()

        logger.debug(
            "CRM message logged: user=%s, dir=%s, id=%s", user_id, direction, message_id
        )
        return message_id


async def get_user_messages(
    user_id: int,
    limit: int = 50,
    direction: MessageDirection | None = None,
) -> list[CrmMessage]:
    """Get CRM messages for a user. Returns list of CrmMessage dicts."""
    async with aiosqlite.connect(DB_PATH) as db:
        if direction:
            query = """
                SELECT id, direction, message_type, text, created_at
                FROM crm_messages
                WHERE user_id = ? AND direction = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [user_id, direction, limit]
        else:
            query = """
                SELECT id, direction, message_type, text, created_at
                FROM crm_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = [user_id, limit]

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        messages = []
        for row in rows:
            messages.append(
                {
                    "id": row[0],
                    "direction": row[1],
                    "message_type": row[2],
                    "text": row[3],
                    "created_at": row[4],
                }
            )

        # Return in chronological order (oldest first)
        return list(reversed(messages))


async def get_user_messages_count(user_id: int) -> int:
    """Count total messages for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM crm_messages WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def has_user_consent(user_id: int) -> bool:
    """Check if user has given consent for message logging."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM crm_events WHERE user_id = ? AND event_type = 'start'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return (row[0] if row else 0) > 0


async def format_messages_for_ai(user_id: int, limit: int = 20) -> str:
    """Format user messages for AI summarization."""
    messages = await get_user_messages(user_id, limit=limit)

    if not messages:
        return ""

    lines = []
    for msg in messages:
        direction = "👤 Клиент" if msg["direction"] == "in" else "🤖 Бот"
        text = msg["text"][:200] + "..." if len(msg["text"]) > 200 else msg["text"]
        timestamp = msg["created_at"][:16] if msg["created_at"] else ""
        lines.append(f"[{timestamp}] {direction}: {text}")

    return "\n".join(lines)
