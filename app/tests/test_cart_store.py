"""Tests for cart storage module."""

import pytest

from app.storage import cart


@pytest.mark.asyncio
async def test_add_to_cart_new_item(user_id: int) -> None:
    """Test adding new item to empty cart."""
    await cart.add_to_cart(user_id, "SKU001", 2)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 2)]


@pytest.mark.asyncio
async def test_add_to_cart_increment(user_id: int) -> None:
    """Test incrementing existing item quantity."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU001", 3)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 5)]


@pytest.mark.asyncio
async def test_add_to_cart_decrement(user_id: int) -> None:
    """Test decrementing item quantity."""
    await cart.add_to_cart(user_id, "SKU001", 5)
    await cart.add_to_cart(user_id, "SKU001", -2)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 3)]


@pytest.mark.asyncio
async def test_add_to_cart_decrement_removes_item(user_id: int) -> None:
    """Test that decrementing below 1 removes item."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU001", -2)

    items = await cart.get_cart(user_id)
    assert items == []


@pytest.mark.asyncio
async def test_add_to_cart_zero_qty_noop(user_id: int) -> None:
    """Test that adding zero quantity does nothing."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU001", 0)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 2)]


@pytest.mark.asyncio
async def test_set_qty(user_id: int) -> None:
    """Test setting specific quantity."""
    await cart.add_to_cart(user_id, "SKU001", 5)
    await cart.set_qty(user_id, "SKU001", 10)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 10)]


@pytest.mark.asyncio
async def test_set_qty_zero_removes(user_id: int) -> None:
    """Test setting quantity to zero removes item."""
    await cart.add_to_cart(user_id, "SKU001", 5)
    await cart.set_qty(user_id, "SKU001", 0)

    items = await cart.get_cart(user_id)
    assert items == []


@pytest.mark.asyncio
async def test_remove_from_cart(user_id: int) -> None:
    """Test removing item from cart."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU002", 3)
    await cart.remove_from_cart(user_id, "SKU001")

    items = await cart.get_cart(user_id)
    assert items == [("SKU002", 3)]


@pytest.mark.asyncio
async def test_clear_cart(user_id: int) -> None:
    """Test clearing entire cart."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU002", 3)
    await cart.clear_cart(user_id)

    items = await cart.get_cart(user_id)
    assert items == []


@pytest.mark.asyncio
async def test_get_cart_empty(user_id: int) -> None:
    """Test getting empty cart."""
    items = await cart.get_cart(user_id)
    assert items == []


@pytest.mark.asyncio
async def test_get_cart_sorted_by_sku(user_id: int) -> None:
    """Test that cart items are sorted by SKU."""
    await cart.add_to_cart(user_id, "SKU003", 1)
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(user_id, "SKU002", 3)

    items = await cart.get_cart(user_id)
    assert items == [("SKU001", 2), ("SKU002", 3), ("SKU003", 1)]


@pytest.mark.asyncio
async def test_cart_isolation_between_users(user_id: int, another_user_id: int) -> None:
    """Test that carts are isolated between users."""
    await cart.add_to_cart(user_id, "SKU001", 2)
    await cart.add_to_cart(another_user_id, "SKU002", 5)

    user1_items = await cart.get_cart(user_id)
    user2_items = await cart.get_cart(another_user_id)

    assert user1_items == [("SKU001", 2)]
    assert user2_items == [("SKU002", 5)]


# Checkout session tests


@pytest.mark.asyncio
async def test_compute_cart_hash_deterministic() -> None:
    """Test that cart hash is deterministic."""
    items = [("SKU001", 2), ("SKU002", 3)]

    hash1 = cart.compute_cart_hash(items)
    hash2 = cart.compute_cart_hash(items)

    assert hash1 == hash2
    assert len(hash1) == 16


@pytest.mark.asyncio
async def test_compute_cart_hash_order_independent() -> None:
    """Test that cart hash is independent of item order."""
    items1 = [("SKU001", 2), ("SKU002", 3)]
    items2 = [("SKU002", 3), ("SKU001", 2)]

    hash1 = cart.compute_cart_hash(items1)
    hash2 = cart.compute_cart_hash(items2)

    assert hash1 == hash2


@pytest.mark.asyncio
async def test_get_or_create_checkout_session_new(user_id: int) -> None:
    """Test creating new checkout session."""
    items = [("SKU001", 2)]

    order_id, is_new = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-12345"
    )

    assert order_id == "ORD-12345"
    assert is_new is True


@pytest.mark.asyncio
async def test_get_or_create_checkout_session_existing(user_id: int) -> None:
    """Test getting existing checkout session."""
    items = [("SKU001", 2)]

    # First call creates
    order_id1, is_new1 = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-12345"
    )
    # Second call returns existing
    order_id2, is_new2 = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-99999"  # Different generator, should be ignored
    )

    assert order_id1 == "ORD-12345"
    assert is_new1 is True
    assert order_id2 == "ORD-12345"
    assert is_new2 is False


@pytest.mark.asyncio
async def test_checkout_session_different_carts(user_id: int) -> None:
    """Test that different cart contents create different sessions."""
    items1 = [("SKU001", 2)]
    items2 = [("SKU001", 3)]  # Different quantity

    order_id1, _ = await cart.get_or_create_checkout_session(
        user_id, items1, lambda: "ORD-11111"
    )
    order_id2, _ = await cart.get_or_create_checkout_session(
        user_id, items2, lambda: "ORD-22222"
    )

    assert order_id1 == "ORD-11111"
    assert order_id2 == "ORD-22222"


@pytest.mark.asyncio
async def test_mark_checkout_complete(user_id: int) -> None:
    """Test marking checkout as complete."""
    items = [("SKU001", 2)]

    order_id, _ = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-12345"
    )
    await cart.mark_checkout_complete(user_id, order_id)

    # Verify we can still get the session (it's completed, not deleted)
    order_id2, is_new = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-99999"
    )
    assert order_id2 == "ORD-12345"
    assert is_new is False


@pytest.mark.asyncio
async def test_cleanup_old_checkout_sessions(user_id: int) -> None:
    """Test cleaning up pending checkout sessions."""
    items = [("SKU001", 2)]

    # Create pending session
    order_id, _ = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-12345"
    )

    # Cleanup pending sessions
    await cart.cleanup_old_checkout_sessions(user_id)

    # New session should be created
    order_id2, is_new = await cart.get_or_create_checkout_session(
        user_id, items, lambda: "ORD-99999"
    )
    assert order_id2 == "ORD-99999"
    assert is_new is True
