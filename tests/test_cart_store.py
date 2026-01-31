"""Tests for cart_store module."""

import asyncio

import aiosqlite
import pytest

# Patch DB path before import
TEST_DB_PATH = None


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    """Set up a temporary database for each test."""
    global TEST_DB_PATH
    TEST_DB_PATH = str(tmp_path / "test_bot.sqlite3")
    monkeypatch.setattr("app.cart_store.DB_PATH", TEST_DB_PATH)


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_init_db(isolate_test_database):
    """Test database initialization."""
    from app import cart_store

    # Use the isolated test database from the fixture
    db_path = isolate_test_database

    await cart_store.init_db()

    # Check tables were created
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}

    assert "cart_items" in tables
    assert "user_mode" in tables
    assert "chat_history" in tables


@pytest.mark.asyncio
async def test_add_to_cart(monkeypatch, tmp_path):
    """Test adding items to cart."""
    from app import cart_store

    db_path = str(tmp_path / "test_add.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123
    sku = "PRD-001"

    # Add item
    await cart_store.add_to_cart(user_id, sku, 5)
    cart = await cart_store.get_cart(user_id)
    assert cart == [(sku, 5)]

    # Add more of same item
    await cart_store.add_to_cart(user_id, sku, 3)
    cart = await cart_store.get_cart(user_id)
    assert cart == [(sku, 8)]


@pytest.mark.asyncio
async def test_add_to_cart_negative(monkeypatch, tmp_path):
    """Test decrementing items in cart."""
    from app import cart_store

    db_path = str(tmp_path / "test_neg.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123
    sku = "PRD-001"

    # Add item
    await cart_store.add_to_cart(user_id, sku, 5)

    # Decrement
    await cart_store.add_to_cart(user_id, sku, -2)
    cart = await cart_store.get_cart(user_id)
    assert cart == [(sku, 3)]

    # Decrement to zero - should remove
    await cart_store.add_to_cart(user_id, sku, -5)
    cart = await cart_store.get_cart(user_id)
    assert cart == []


@pytest.mark.asyncio
async def test_remove_from_cart(monkeypatch, tmp_path):
    """Test removing items from cart."""
    from app import cart_store

    db_path = str(tmp_path / "test_remove.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123

    await cart_store.add_to_cart(user_id, "PRD-001", 5)
    await cart_store.add_to_cart(user_id, "PRD-002", 3)

    await cart_store.remove_from_cart(user_id, "PRD-001")
    cart = await cart_store.get_cart(user_id)
    assert cart == [("PRD-002", 3)]


@pytest.mark.asyncio
async def test_clear_cart(monkeypatch, tmp_path):
    """Test clearing cart."""
    from app import cart_store

    db_path = str(tmp_path / "test_clear.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123

    await cart_store.add_to_cart(user_id, "PRD-001", 5)
    await cart_store.add_to_cart(user_id, "PRD-002", 3)

    await cart_store.clear_cart(user_id)
    cart = await cart_store.get_cart(user_id)
    assert cart == []


@pytest.mark.asyncio
async def test_set_qty(monkeypatch, tmp_path):
    """Test setting exact quantity."""
    from app import cart_store

    db_path = str(tmp_path / "test_qty.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123
    sku = "PRD-001"

    # Set initial qty
    await cart_store.set_qty(user_id, sku, 10)
    cart = await cart_store.get_cart(user_id)
    assert cart == [(sku, 10)]

    # Change qty
    await cart_store.set_qty(user_id, sku, 5)
    cart = await cart_store.get_cart(user_id)
    assert cart == [(sku, 5)]

    # Set to zero - should remove
    await cart_store.set_qty(user_id, sku, 0)
    cart = await cart_store.get_cart(user_id)
    assert cart == []


@pytest.mark.asyncio
async def test_ai_mode(monkeypatch, tmp_path):
    """Test AI mode toggle."""
    from app import cart_store

    db_path = str(tmp_path / "test_ai.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123

    # Default should be False
    assert await cart_store.get_ai_mode(user_id) == False

    # Enable AI mode
    await cart_store.set_ai_mode(user_id, True)
    assert await cart_store.get_ai_mode(user_id) == True

    # Disable AI mode
    await cart_store.set_ai_mode(user_id, False)
    assert await cart_store.get_ai_mode(user_id) == False


@pytest.mark.asyncio
async def test_chat_history(monkeypatch, tmp_path):
    """Test chat history management."""
    from app import cart_store

    db_path = str(tmp_path / "test_chat.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user_id = 123

    # Add messages
    await cart_store.add_chat_message(user_id, "user", "Hello")
    await cart_store.add_chat_message(user_id, "assistant", "Hi there!")

    history = await cart_store.get_chat_history(user_id)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "Hello"}
    assert history[1] == {"role": "assistant", "content": "Hi there!"}

    # Clear history
    await cart_store.clear_chat_history(user_id)
    history = await cart_store.get_chat_history(user_id)
    assert len(history) == 0


@pytest.mark.asyncio
async def test_chat_history_limit(monkeypatch, isolate_test_database):
    """Test chat history respects max limit."""
    from app import cart_store

    # Patch MAX_HISTORY_MESSAGES in the actual module where it's used
    monkeypatch.setattr("app.storage.chat_history.MAX_HISTORY_MESSAGES", 5)
    await cart_store.init_db()

    user_id = 123

    # Add more than limit
    for i in range(10):
        await cart_store.add_chat_message(user_id, "user", f"Message {i}")

    history = await cart_store.get_chat_history(user_id)
    assert len(history) == 5
    # Should keep most recent
    assert history[-1]["content"] == "Message 9"


@pytest.mark.asyncio
async def test_multiple_users(monkeypatch, tmp_path):
    """Test cart isolation between users."""
    from app import cart_store

    db_path = str(tmp_path / "test_users.sqlite3")
    monkeypatch.setattr(cart_store, "DB_PATH", db_path)
    await cart_store.init_db()

    user1 = 111
    user2 = 222

    await cart_store.add_to_cart(user1, "PRD-001", 5)
    await cart_store.add_to_cart(user2, "PRD-002", 3)

    cart1 = await cart_store.get_cart(user1)
    cart2 = await cart_store.get_cart(user2)

    assert cart1 == [("PRD-001", 5)]
    assert cart2 == [("PRD-002", 3)]
