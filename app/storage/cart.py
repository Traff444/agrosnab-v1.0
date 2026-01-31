"""Cart and checkout session storage."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import aiosqlite

from .db import DB_PATH

logger = logging.getLogger(__name__)


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
    """Set specific quantity for item in cart."""
    async with aiosqlite.connect(DB_PATH) as db:
        if qty <= 0:
            await db.execute(
                "DELETE FROM cart_items WHERE user_id=? AND sku=?", (user_id, sku)
            )
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
        await db.execute(
            "DELETE FROM cart_items WHERE user_id=? AND sku=?", (user_id, sku)
        )
        await db.commit()


async def clear_cart(user_id: int) -> None:
    """Clear all items from cart."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
        await db.commit()


async def get_cart(user_id: int) -> list[tuple[str, int]]:
    """Get cart contents as list of (sku, qty) tuples."""
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
            logger.info(
                "Found existing checkout session for user %s: order_id=%s",
                user_id,
                row[0],
            )
            return row[0], False

        # Create new session
        order_id = order_id_generator()
        await db.execute(
            "INSERT INTO checkout_sessions(user_id, cart_hash, order_id, status) VALUES(?, ?, ?, 'pending')",
            (user_id, cart_hash, order_id),
        )
        await db.commit()
        logger.info(
            "Created new checkout session for user %s: order_id=%s", user_id, order_id
        )
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
