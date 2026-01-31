"""Tests for CRM functionality in cart_store module."""

import asyncio
from datetime import date

import aiosqlite
import pytest


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_log_crm_event(monkeypatch, tmp_path):
    """Test logging CRM events."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_event.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Log a start event
    event_id = await cart_store.log_crm_event(
        user_id,
        "start",
        {
            "username": "testuser",
            "first_name": "Test",
        },
    )

    assert event_id > 0

    # Verify event was stored
    events = await cart_store.get_user_events(user_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "start"
    assert events[0]["payload"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_get_user_events_with_filter(monkeypatch, tmp_path):
    """Test getting events with type filter."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_filter.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Log multiple events
    await cart_store.log_crm_event(user_id, "start", {})
    await cart_store.log_crm_event(user_id, "catalog_view", {"category": "all"})
    await cart_store.log_crm_event(user_id, "add_to_cart", {"sku": "ABC-001"})
    await cart_store.log_crm_event(user_id, "catalog_view", {"category": "Овощи"})

    # Get all events
    all_events = await cart_store.get_user_events(user_id)
    assert len(all_events) == 4

    # Filter by type
    catalog_events = await cart_store.get_user_events(user_id, event_types=["catalog_view"])
    assert len(catalog_events) == 2
    assert all(e["event_type"] == "catalog_view" for e in catalog_events)


@pytest.mark.asyncio
async def test_get_user_stage(monkeypatch, tmp_path):
    """Test computing user stage from events."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_stage.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # No events - no stage
    stage = await cart_store.get_user_stage(user_id)
    assert stage is None

    # Only start event - stage is 'new'
    await cart_store.log_crm_event(user_id, "start", {})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "new"

    # Add catalog view - stage is 'engaged'
    await cart_store.log_crm_event(user_id, "catalog_view", {})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "engaged"

    # Add to cart - stage is 'cart'
    await cart_store.log_crm_event(user_id, "add_to_cart", {"sku": "ABC"})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "cart"


@pytest.mark.asyncio
async def test_compute_stage_only_increases(monkeypatch, tmp_path):
    """Test that stage only goes up, never down."""
    from app import cart_store

    # Test the compute_stage function directly
    assert cart_store.compute_stage(None, "new") == "new"
    assert cart_store.compute_stage("new", "engaged") == "engaged"
    assert cart_store.compute_stage("engaged", "cart") == "cart"
    assert cart_store.compute_stage("cart", "checkout") == "checkout"
    assert cart_store.compute_stage("checkout", "customer") == "customer"
    assert cart_store.compute_stage("customer", "repeat") == "repeat"

    # Stage should NOT decrease
    assert cart_store.compute_stage("customer", "new") == "customer"
    assert cart_store.compute_stage("customer", "engaged") == "customer"
    assert cart_store.compute_stage("customer", "cart") == "customer"
    assert cart_store.compute_stage("repeat", "customer") == "repeat"


@pytest.mark.asyncio
async def test_get_user_orders_count(monkeypatch, tmp_path):
    """Test counting user orders."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_orders.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # No orders initially
    count = await cart_store.get_user_orders_count(user_id)
    assert count == 0

    # Add some orders
    await cart_store.log_crm_event(user_id, "order_created", {"order_id": "ORD-001", "total": 5000})
    count = await cart_store.get_user_orders_count(user_id)
    assert count == 1

    await cart_store.log_crm_event(user_id, "order_created", {"order_id": "ORD-002", "total": 3000})
    count = await cart_store.get_user_orders_count(user_id)
    assert count == 2


@pytest.mark.asyncio
async def test_get_daily_stats(monkeypatch, tmp_path):
    """Test daily statistics calculation."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_stats.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    today = date.today().isoformat()

    # Create events for multiple users
    await cart_store.log_crm_event(1001, "start", {})
    await cart_store.log_crm_event(1002, "start", {})
    await cart_store.log_crm_event(1003, "start", {})

    await cart_store.log_crm_event(1001, "catalog_view", {})
    await cart_store.log_crm_event(1002, "catalog_view", {})

    await cart_store.log_crm_event(1001, "add_to_cart", {"sku": "ABC"})

    await cart_store.log_crm_event(1001, "checkout_started", {})

    await cart_store.log_crm_event(1001, "order_created", {"total": 5000})

    # Get stats
    stats = await cart_store.get_daily_stats(today)

    assert stats["visitors"] == 3
    assert stats["engaged"] == 2
    assert stats["cart"] == 1
    assert stats["checkout"] == 1
    assert stats["orders"] == 1
    assert stats["orders_total"] == 5000


@pytest.mark.asyncio
async def test_get_first_last_seen(monkeypatch, tmp_path):
    """Test first_seen and last_seen timestamps."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_seen.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # No events - no timestamps
    first = await cart_store.get_first_seen(user_id)
    last = await cart_store.get_last_seen(user_id)
    assert first is None
    assert last is None

    # Add first event
    await cart_store.log_crm_event(user_id, "start", {})
    first = await cart_store.get_first_seen(user_id)
    last = await cart_store.get_last_seen(user_id)
    assert first is not None
    assert last is not None
    assert first == last  # Same event

    # Add another event (timestamps may be same due to SQLite second precision)
    await cart_store.log_crm_event(user_id, "catalog_view", {})

    first2 = await cart_store.get_first_seen(user_id)
    last2 = await cart_store.get_last_seen(user_id)

    assert first2 == first  # First seen should not change
    assert last2 is not None  # Last seen should exist
    # Note: last2 may equal first if both events in same second - that's OK


@pytest.mark.asyncio
async def test_full_customer_journey(monkeypatch, tmp_path):
    """Integration test: full customer journey through funnel."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_journey.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 999999

    # 1. /start
    await cart_store.log_crm_event(
        user_id,
        "start",
        {
            "username": "test_customer",
            "first_name": "Test",
        },
    )
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "new"

    # 2. View catalog
    await cart_store.log_crm_event(user_id, "catalog_view", {"category": "all"})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "engaged"

    # 3. Search for product
    await cart_store.log_crm_event(user_id, "search", {"query": "помидоры"})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "engaged"  # Still engaged

    # 4. View product detail
    await cart_store.log_crm_event(user_id, "product_view", {"sku": "TOM-001"})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "engaged"  # Still engaged

    # 5. Add to cart
    await cart_store.log_crm_event(user_id, "add_to_cart", {"sku": "TOM-001", "qty": 5})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "cart"

    # 6. Start checkout
    await cart_store.log_crm_event(user_id, "checkout_started", {"phone": "+7999***"})
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "checkout"

    # 7. Complete order
    await cart_store.log_crm_event(
        user_id,
        "order_created",
        {
            "order_id": "ORD-TEST-001",
            "total": 5000,
            "items_count": 1,
        },
    )
    stage = await cart_store.get_user_stage(user_id)
    assert stage == "customer"

    # Verify order count
    orders_count = await cart_store.get_user_orders_count(user_id)
    assert orders_count == 1

    # 8. Second order - becomes repeat customer
    await cart_store.log_crm_event(
        user_id,
        "order_created",
        {
            "order_id": "ORD-TEST-002",
            "total": 3000,
        },
    )

    orders_count = await cart_store.get_user_orders_count(user_id)
    assert orders_count == 2

    # Verify all events recorded
    events = await cart_store.get_user_events(user_id)
    assert len(events) == 8

    # Verify event types
    event_types = [e["event_type"] for e in events]
    assert "start" in event_types
    assert "catalog_view" in event_types
    assert "search" in event_types
    assert "product_view" in event_types
    assert "add_to_cart" in event_types
    assert "checkout_started" in event_types
    assert "order_created" in event_types


@pytest.mark.asyncio
async def test_crm_events_isolation(monkeypatch, tmp_path):
    """Test that CRM events are isolated per user."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_isolation.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user1 = 1111
    user2 = 2222

    await cart_store.log_crm_event(user1, "start", {})
    await cart_store.log_crm_event(user1, "order_created", {"total": 10000})

    await cart_store.log_crm_event(user2, "start", {})
    await cart_store.log_crm_event(user2, "catalog_view", {})

    # User 1 should be customer with 1 order
    stage1 = await cart_store.get_user_stage(user1)
    orders1 = await cart_store.get_user_orders_count(user1)
    assert stage1 == "customer"
    assert orders1 == 1

    # User 2 should be engaged with 0 orders
    stage2 = await cart_store.get_user_stage(user2)
    orders2 = await cart_store.get_user_orders_count(user2)
    assert stage2 == "engaged"
    assert orders2 == 0


@pytest.mark.asyncio
async def test_crm_events_table_created(isolate_test_database):
    """Test that crm_events table is created on init."""
    from app import cart_store

    # Use the isolated test database from the fixture
    db_path = isolate_test_database

    await cart_store.init_db()

    # Check table exists
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crm_events'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "crm_events"

        # Check indexes exist
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_crm_events%'"
        )
        indexes = [row[0] for row in await cursor.fetchall()]
        assert "idx_crm_events_user" in indexes
        assert "idx_crm_events_type" in indexes


# =============================================================================
# Phase 3: CRM Messages Tests
# =============================================================================


@pytest.mark.asyncio
async def test_crm_messages_table_created(isolate_test_database):
    """Test that crm_messages table is created on init."""
    from app import cart_store

    # Use the isolated test database from the fixture
    db_path = isolate_test_database

    await cart_store.init_db()

    # Check table exists
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crm_messages'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "crm_messages"

        # Check index exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_crm_messages_user'"
        )
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_log_crm_message(monkeypatch, tmp_path):
    """Test logging CRM messages."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_log_msg.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Log incoming message
    msg_id = await cart_store.log_crm_message(
        user_id=user_id,
        direction="in",
        text="Привет, что у вас есть?",
        message_type="text",
    )

    assert msg_id > 0

    # Verify message was stored
    messages = await cart_store.get_user_messages(user_id)
    assert len(messages) == 1
    assert messages[0]["direction"] == "in"
    assert messages[0]["text"] == "Привет, что у вас есть?"
    assert messages[0]["message_type"] == "text"


@pytest.mark.asyncio
async def test_get_user_messages_with_direction_filter(monkeypatch, tmp_path):
    """Test getting messages filtered by direction."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_msg_filter.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Log multiple messages
    await cart_store.log_crm_message(user_id, "in", "Сообщение 1")
    await cart_store.log_crm_message(user_id, "out", "Ответ 1")
    await cart_store.log_crm_message(user_id, "in", "Сообщение 2")
    await cart_store.log_crm_message(user_id, "out", "Ответ 2")

    # Get all messages
    all_msgs = await cart_store.get_user_messages(user_id)
    assert len(all_msgs) == 4

    # Filter by direction
    in_msgs = await cart_store.get_user_messages(user_id, direction="in")
    assert len(in_msgs) == 2
    assert all(m["direction"] == "in" for m in in_msgs)

    out_msgs = await cart_store.get_user_messages(user_id, direction="out")
    assert len(out_msgs) == 2
    assert all(m["direction"] == "out" for m in out_msgs)


@pytest.mark.asyncio
async def test_get_user_messages_count(monkeypatch, tmp_path):
    """Test counting user messages."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_msg_count.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # No messages initially
    count = await cart_store.get_user_messages_count(user_id)
    assert count == 0

    # Add messages
    await cart_store.log_crm_message(user_id, "in", "Msg 1")
    count = await cart_store.get_user_messages_count(user_id)
    assert count == 1

    await cart_store.log_crm_message(user_id, "out", "Msg 2")
    await cart_store.log_crm_message(user_id, "in", "Msg 3")
    count = await cart_store.get_user_messages_count(user_id)
    assert count == 3


@pytest.mark.asyncio
async def test_has_user_consent(monkeypatch, tmp_path):
    """Test checking user consent."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_consent.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # No consent initially (no start event)
    has_consent = await cart_store.has_user_consent(user_id)
    assert has_consent is False

    # Add start event (implies consent)
    await cart_store.log_crm_event(user_id, "start", {"consent": True})
    has_consent = await cart_store.has_user_consent(user_id)
    assert has_consent is True


@pytest.mark.asyncio
async def test_format_messages_for_ai(monkeypatch, tmp_path):
    """Test formatting messages for AI context."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_format_ai.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Add messages
    await cart_store.log_crm_message(user_id, "in", "Что есть?")
    await cart_store.log_crm_message(user_id, "out", "У нас есть махорка!")
    await cart_store.log_crm_message(user_id, "in", "Добавь 5 штук")

    # Format for AI
    formatted = await cart_store.format_messages_for_ai(user_id, limit=10)

    assert "Что есть?" in formatted
    assert "У нас есть махорка!" in formatted
    assert "Добавь 5 штук" in formatted
    assert "Клиент:" in formatted
    assert "Бот:" in formatted  # AI responses marked as 'Бот'


@pytest.mark.asyncio
async def test_crm_messages_isolation(monkeypatch, tmp_path):
    """Test that CRM messages are isolated per user."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_msg_isolation.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user1 = 1111
    user2 = 2222

    await cart_store.log_crm_message(user1, "in", "User 1 msg 1")
    await cart_store.log_crm_message(user1, "in", "User 1 msg 2")

    await cart_store.log_crm_message(user2, "in", "User 2 msg")

    # User 1 should have 2 messages
    count1 = await cart_store.get_user_messages_count(user1)
    assert count1 == 2

    # User 2 should have 1 message
    count2 = await cart_store.get_user_messages_count(user2)
    assert count2 == 1

    # Messages should be isolated
    msgs1 = await cart_store.get_user_messages(user1)
    assert all("User 1" in m["text"] for m in msgs1)

    msgs2 = await cart_store.get_user_messages(user2)
    assert all("User 2" in m["text"] for m in msgs2)


@pytest.mark.asyncio
async def test_crm_message_truncation(monkeypatch, tmp_path):
    """Test that long messages are truncated."""
    from app import cart_store

    db_path = str(tmp_path / "test_crm_msg_truncate.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123456

    # Create a very long message
    long_text = "A" * 5000

    msg_id = await cart_store.log_crm_message(user_id, "in", long_text)
    assert msg_id > 0

    # Verify message was truncated
    messages = await cart_store.get_user_messages(user_id)
    assert len(messages) == 1
    # Message should be truncated to 2000 chars + '...' = 2003
    assert len(messages[0]["text"]) <= 2003
    assert messages[0]["text"].endswith("...")
