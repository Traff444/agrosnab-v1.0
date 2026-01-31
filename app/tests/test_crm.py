"""Tests for CRM storage module."""

import pytest

from app.storage import crm


@pytest.mark.asyncio
async def test_log_crm_event(user_id: int) -> None:
    """Test logging CRM event."""
    await crm.log_crm_event(user_id, "page_view", {"page": "catalog"})

    events = await crm.get_user_events(user_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "page_view"
    assert events[0]["payload"]["page"] == "catalog"


@pytest.mark.asyncio
async def test_log_crm_event_no_payload(user_id: int) -> None:
    """Test logging CRM event without payload."""
    await crm.log_crm_event(user_id, "session_start", None)

    events = await crm.get_user_events(user_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "session_start"
    assert events[0]["payload"] is None


@pytest.mark.asyncio
async def test_get_user_events_filtered(user_id: int) -> None:
    """Test getting filtered events by type."""
    await crm.log_crm_event(user_id, "page_view", {"page": "catalog"})
    await crm.log_crm_event(user_id, "add_to_cart", {"sku": "SKU001"})
    await crm.log_crm_event(user_id, "page_view", {"page": "product"})

    events = await crm.get_user_events(user_id, event_types=["add_to_cart"])
    assert len(events) == 1
    assert events[0]["event_type"] == "add_to_cart"


@pytest.mark.asyncio
async def test_get_user_events_limit(user_id: int) -> None:
    """Test getting events with limit."""
    for i in range(5):
        await crm.log_crm_event(user_id, "page_view", {"page": f"page_{i}"})

    events = await crm.get_user_events(user_id, limit=3)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_get_user_events_empty(user_id: int) -> None:
    """Test getting events for user with no events."""
    events = await crm.get_user_events(user_id)
    assert events == []


@pytest.mark.asyncio
async def test_get_user_orders_count(user_id: int) -> None:
    """Test counting user orders."""
    # No orders
    count = await crm.get_user_orders_count(user_id)
    assert count == 0

    # Add some order events
    await crm.log_crm_event(user_id, "order_created", {"order_id": "ORD-001"})
    await crm.log_crm_event(user_id, "order_created", {"order_id": "ORD-002"})

    count = await crm.get_user_orders_count(user_id)
    assert count == 2


@pytest.mark.asyncio
async def test_log_crm_message(user_id: int) -> None:
    """Test logging CRM message."""
    await crm.log_crm_message(user_id, "inbound", "Hello!")
    await crm.log_crm_message(user_id, "outbound", "Hi there!")

    messages = await crm.get_user_messages(user_id)
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_get_user_messages_limit(user_id: int) -> None:
    """Test getting messages with limit."""
    for i in range(10):
        await crm.log_crm_message(user_id, "inbound", f"Message {i}")

    messages = await crm.get_user_messages(user_id, limit=5)
    assert len(messages) == 5


@pytest.mark.asyncio
async def test_events_isolation_between_users(user_id: int, another_user_id: int) -> None:
    """Test that events are isolated between users."""
    await crm.log_crm_event(user_id, "page_view", {"page": "catalog"})
    await crm.log_crm_event(another_user_id, "add_to_cart", {"sku": "SKU001"})

    user1_events = await crm.get_user_events(user_id)
    user2_events = await crm.get_user_events(another_user_id)

    assert len(user1_events) == 1
    assert user1_events[0]["event_type"] == "page_view"

    assert len(user2_events) == 1
    assert user2_events[0]["event_type"] == "add_to_cart"
