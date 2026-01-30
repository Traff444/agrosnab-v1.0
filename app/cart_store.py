from __future__ import annotations

from datetime import date
import hashlib
import json
import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# CRM Stage priorities (higher = further in funnel)
STAGE_PRIORITY = {
    'new': 1,
    'engaged': 2,
    'cart': 3,
    'checkout': 4,
    'customer': 5,
    'repeat': 6,
}

# Event to stage mapping
EVENT_TO_STAGE = {
    'start': 'new',
    'catalog_view': 'engaged',
    'product_view': 'engaged',
    'search': 'engaged',
    'add_to_cart': 'cart',
    'checkout_started': 'checkout',
    'order_created': 'customer',  # or 'repeat' if orders_count >= 2
}

import os
from pathlib import Path

# Use relative path for local development, absolute for Docker
_DATA_DIR = Path(__file__).parent.parent / "data"
if os.path.exists("/app/data"):
    DB_PATH = "/app/data/bot.sqlite3"
else:
    _DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = str(_DATA_DIR / "bot.sqlite3")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_mode (
                user_id INTEGER PRIMARY KEY,
                ai_mode INTEGER NOT NULL DEFAULT 0
            );
            """
        )
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
        # CRM messages table (Phase 3)
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


MAX_HISTORY_MESSAGES = 20  # Хранить последние 20 сообщений


async def add_chat_message(user_id: int, role: str, content: str) -> None:
    """Add a message to chat history. Role: 'user' or 'assistant' or 'system'"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history(user_id, role, content) VALUES(?, ?, ?)",
            (user_id, role, content),
        )
        # Удаляем старые сообщения, оставляем только последние N
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_mode(user_id, ai_mode) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET ai_mode=excluded.ai_mode",
            (user_id, 1 if enabled else 0),
        )
        await db.commit()


async def get_ai_mode(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT ai_mode FROM user_mode WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row[0]) if row else False


async def add_to_cart(user_id: int, sku: str, qty: int) -> None:
    """Add qty to cart. Supports negative qty for decrement."""
    if qty == 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        if qty > 0:
            await db.execute(
                "INSERT INTO cart_items(user_id, sku, qty) VALUES(?, ?, ?) "
                "ON CONFLICT(user_id, sku) DO UPDATE SET qty=cart_items.qty + excluded.qty",
                (user_id, sku, qty),
            )
        else:
            # Decrement: update and remove if zero or negative
            await db.execute(
                "UPDATE cart_items SET qty = qty + ? WHERE user_id = ? AND sku = ?",
                (qty, user_id, sku),
            )
            await db.execute(
                "DELETE FROM cart_items WHERE user_id = ? AND sku = ? AND qty <= 0",
                (user_id, sku),
            )
        await db.commit()


async def set_qty(user_id: int, sku: str, qty: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if qty <= 0:
            await db.execute("DELETE FROM cart_items WHERE user_id=? AND sku=?", (user_id, sku))
        else:
            await db.execute(
                "INSERT INTO cart_items(user_id, sku, qty) VALUES(?, ?, ?) "
                "ON CONFLICT(user_id, sku) DO UPDATE SET qty=excluded.qty",
                (user_id, sku, qty),
            )
        await db.commit()


async def remove_from_cart(user_id: int, sku: str) -> None:
    """Remove item from cart entirely."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id=? AND sku=?", (user_id, sku))
        await db.commit()


async def clear_cart(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
        await db.commit()


async def get_cart(user_id: int) -> list[tuple[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT sku, qty FROM cart_items WHERE user_id=? ORDER BY sku", (user_id,)
        )
        rows = await cur.fetchall()
        return [(r[0], int(r[1])) for r in rows]


# ---------------------------------------------------------------------------
# Checkout session helpers (idempotency)
# ---------------------------------------------------------------------------
def compute_cart_hash(cart_items: list[tuple[str, int]]) -> str:
    """Compute a stable hash for cart contents to detect duplicate checkouts."""
    # Sort to ensure consistent ordering
    data = json.dumps(sorted(cart_items), sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


async def get_or_create_checkout_session(
    user_id: int,
    cart_items: list[tuple[str, int]],
    order_id_generator: Any,
) -> tuple[str, bool]:
    """
    Get existing checkout session or create new one.
    Returns (order_id, is_new).
    """
    cart_hash = compute_cart_hash(cart_items)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT order_id, status FROM checkout_sessions WHERE user_id = ? AND cart_hash = ?",
            (user_id, cart_hash),
        )
        row = await cur.fetchone()

        if row:
            # Return existing session's order_id
            logger.info(f"Found existing checkout session for user {user_id}: order_id={row[0]}")
            return row[0], False

        # Create new session
        order_id = order_id_generator()
        await db.execute(
            "INSERT INTO checkout_sessions(user_id, cart_hash, order_id, status) VALUES(?, ?, ?, 'pending')",
            (user_id, cart_hash, order_id),
        )
        await db.commit()
        logger.info(f"Created new checkout session for user {user_id}: order_id={order_id}")
        return order_id, True


async def mark_checkout_complete(user_id: int, order_id: str) -> None:
    """Mark checkout session as completed."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE checkout_sessions SET status = 'completed' WHERE user_id = ? AND order_id = ?",
            (user_id, order_id),
        )
        await db.commit()


async def cleanup_old_checkout_sessions(user_id: int) -> None:
    """Remove old pending checkout sessions after successful order."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM checkout_sessions WHERE user_id = ? AND status = 'pending'",
            (user_id,),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# CRM Events (Phase 1)
# ---------------------------------------------------------------------------

async def log_crm_event(
    user_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None
) -> int:
    """
    Log a CRM event to SQLite.
    Returns the event_id.
    """
    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO crm_events(user_id, event_type, payload_json) VALUES(?, ?, ?)",
            (user_id, event_type, payload_json),
        )
        event_id = cursor.lastrowid
        await db.commit()
        logger.debug(f"CRM event logged: user={user_id}, type={event_type}, id={event_id}")
        return event_id


async def get_user_events(
    user_id: int,
    limit: int = 50,
    event_types: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Get CRM events for a user.
    Returns list of {id, event_type, payload, created_at}.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if event_types:
            placeholders = ','.join('?' * len(event_types))
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
            events.append({
                'id': row[0],
                'event_type': row[1],
                'payload': payload,
                'created_at': row[3],
            })
        return events


async def get_user_stage(user_id: int) -> str | None:
    """
    Calculate current CRM stage for user based on their events.
    Returns highest stage reached or None if no events.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT event_type
            FROM crm_events
            WHERE user_id = ?
            """,
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


async def get_daily_stats(target_date: str | date | None = None) -> dict[str, int]:
    """
    Get CRM statistics for a specific day.
    Returns: {visitors, engaged, cart, checkout, orders, orders_total}
    """
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        # Count unique users per event type for the day
        stats = {
            'date': target_date,
            'visitors': 0,
            'engaged': 0,
            'cart': 0,
            'checkout': 0,
            'orders': 0,
            'orders_total': 0,
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
        stats['visitors'] = row[0] if row else 0

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
        stats['engaged'] = row[0] if row else 0

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
        stats['cart'] = row[0] if row else 0

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
        stats['checkout'] = row[0] if row else 0

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
        stats['orders'] = len(order_rows)

        total = 0
        for row in order_rows:
            if row[0]:
                try:
                    payload = json.loads(row[0])
                    total += payload.get('total', 0)
                except Exception:
                    pass
        stats['orders_total'] = total

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


def compute_stage(current_stage: str | None, new_stage: str) -> str:
    """
    Compute resulting stage. Stage only goes UP, never down.
    """
    if current_stage is None:
        return new_stage

    current_priority = STAGE_PRIORITY.get(current_stage, 0)
    new_priority = STAGE_PRIORITY.get(new_stage, 0)

    if new_priority > current_priority:
        return new_stage
    return current_stage


# ---------------------------------------------------------------------------
# CRM Messages (Phase 3 - Conversation Logging)
# ---------------------------------------------------------------------------

MAX_CRM_MESSAGES = 100  # Store last 100 messages per user


async def log_crm_message(
    user_id: int,
    direction: str,  # 'in' (from user) or 'out' (to user)
    text: str,
    message_type: str = 'text',  # 'text', 'photo', 'voice', 'command'
) -> int:
    """
    Log a message to CRM history.
    Returns the message_id.
    Only logs if user has given consent (checked by caller).
    """
    # Truncate very long messages
    if len(text) > 2000:
        text = text[:2000] + '...'

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

        logger.debug(f"CRM message logged: user={user_id}, dir={direction}, id={message_id}")
        return message_id


async def get_user_messages(
    user_id: int,
    limit: int = 50,
    direction: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get CRM messages for a user.
    Returns list of {id, direction, message_type, text, created_at}.
    """
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
            messages.append({
                'id': row[0],
                'direction': row[1],
                'message_type': row[2],
                'text': row[3],
                'created_at': row[4],
            })

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
    """
    Check if user has given consent for message logging.
    This checks if user has a 'start' event (which implies consent).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM crm_events WHERE user_id = ? AND event_type = 'start'",
            (user_id,),
        )
        row = await cursor.fetchone()
        return (row[0] if row else 0) > 0


async def format_messages_for_ai(user_id: int, limit: int = 20) -> str:
    """
    Format user messages for AI summarization.
    Returns formatted conversation string.
    """
    messages = await get_user_messages(user_id, limit=limit)

    if not messages:
        return ""

    lines = []
    for msg in messages:
        direction = "👤 Клиент" if msg['direction'] == 'in' else "🤖 Бот"
        text = msg['text'][:200] + '...' if len(msg['text']) > 200 else msg['text']
        timestamp = msg['created_at'][:16] if msg['created_at'] else ''
        lines.append(f"[{timestamp}] {direction}: {text}")

    return "\n".join(lines)
