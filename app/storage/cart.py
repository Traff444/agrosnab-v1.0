"""Cart and checkout session storage."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable, Coroutine

import aiosqlite

from .db import DB_PATH

logger = logging.getLogger(__name__)

# Type aliases for clarity
CartItem = tuple[str, int]  # (sku, qty)
OrderIdGenerator = Callable[[], str] | Callable[[], Coroutine]


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
    """Clear all items from cart."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
        await db.commit()


async def get_cart(user_id: int) -> list[CartItem]:
    """Get cart contents as list of (sku, qty) tuples."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT sku, qty FROM cart_items WHERE user_id=? ORDER BY sku", (user_id,)
        )
        rows = await cur.fetchall()
        return [(r[0], int(r[1])) for r in rows]


async def get_cart_count(user_id: int) -> int:
    """Get total quantity of items in cart."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def get_cart_items_count(user_id: int) -> int:
    """Get number of unique items (SKUs) in cart."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM cart_items WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Checkout session helpers (idempotency)
# ---------------------------------------------------------------------------


def compute_cart_hash(cart_items: list[CartItem]) -> str:
    """Compute a stable hash for cart contents to detect duplicate checkouts."""
    data = json.dumps(sorted(cart_items), sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


async def generate_sequential_order_id(user_id: int = 0) -> str:
    """Generate sequential order ID like ORD-000001, ORD-000002..."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(MAX(order_number), 0) FROM order_counter"
        )
        row = await cur.fetchone()
        next_num = (row[0] if row else 0) + 1
        order_id = f"ORD-{next_num:06d}"

        await db.execute(
            "INSERT INTO order_counter(order_number, order_id, user_id) VALUES(?, ?, ?)",
            (next_num, order_id, user_id),
        )
        await db.commit()
        return order_id


async def get_or_create_checkout_session(
    user_id: int,
    cart_items: list[CartItem],
    order_id_generator: OrderIdGenerator,
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
        result = order_id_generator()
        order_id = await result if asyncio.iscoroutine(result) else result
        await db.execute(
            "INSERT INTO checkout_sessions(user_id, cart_hash, order_id, status) VALUES(?, ?, ?, 'pending')",
            (user_id, cart_hash, order_id),
        )
        await db.commit()
        logger.info("Created new checkout session for user %s: order_id=%s", user_id, order_id)
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
# User profiles — remember phone, FIO, address between orders
# ---------------------------------------------------------------------------

async def get_user_profile(user_id: int) -> dict[str, str]:
    """Get saved user profile (phone, fio, last_address)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT phone, fio, last_address FROM user_profiles WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if row:
            return {
                "phone": row["phone"] or "",
                "fio": row["fio"] or "",
                "last_address": row["last_address"] or "",
            }
        return {"phone": "", "fio": "", "last_address": ""}


async def save_user_order(
    user_id: int, order_id: str, items: list[CartItem],
) -> None:
    """Save completed order for 'repeat last order' feature."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_orders(user_id, order_id, items_json) VALUES(?, ?, ?)",
            (user_id, order_id, json.dumps(items)),
        )
        await db.commit()


async def get_last_user_order(user_id: int) -> list[CartItem] | None:
    """Return items from the user's most recent order, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT items_json FROM user_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return json.loads(row[0])


async def save_user_profile(
    user_id: int,
    phone: str | None = None,
    fio: str | None = None,
    last_address: str | None = None,
) -> None:
    """Save/update user profile fields (only non-None fields are updated)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id FROM user_profiles WHERE user_id = ?", (user_id,)
        )
        exists = await cur.fetchone()

        if exists:
            updates = []
            values = []
            if phone is not None:
                updates.append("phone = ?")
                values.append(phone)
            if fio is not None:
                updates.append("fio = ?")
                values.append(fio)
            if last_address is not None:
                updates.append("last_address = ?")
                values.append(last_address)
            if updates:
                updates.append("updated_at = CURRENT_TIMESTAMP")
                values.append(user_id)
                await db.execute(
                    f"UPDATE user_profiles SET {', '.join(updates)} WHERE user_id = ?",
                    values,
                )
        else:
            await db.execute(
                "INSERT INTO user_profiles(user_id, phone, fio, last_address) VALUES(?, ?, ?, ?)",
                (user_id, phone or "", fio or "", last_address or ""),
            )
        await db.commit()
