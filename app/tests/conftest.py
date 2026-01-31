"""Test fixtures for Shop Bot."""

import asyncio
import os
import tempfile
from typing import AsyncGenerator, Generator

import aiosqlite
import pytest
import pytest_asyncio

# Set test database path BEFORE any imports from app.storage
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.environ["SHOP_BOT_TEST_DB_PATH"] = _test_db_path

# Now we can import storage modules
from app.storage.db import DB_PATH, init_db


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def database() -> AsyncGenerator[str, None]:
    """Initialize test database once per session."""
    await init_db()
    yield DB_PATH

    # Cleanup after all tests
    os.close(_test_db_fd)
    os.unlink(_test_db_path)


@pytest_asyncio.fixture(autouse=True)
async def clean_database(database: str) -> AsyncGenerator[None, None]:
    """Clean database before each test."""
    async with aiosqlite.connect(database) as db:
        await db.execute("DELETE FROM cart_items")
        await db.execute("DELETE FROM checkout_sessions")
        await db.execute("DELETE FROM crm_events")
        await db.execute("DELETE FROM crm_messages")
        await db.execute("DELETE FROM chat_history")
        await db.commit()

    yield


@pytest.fixture
def user_id() -> int:
    """Test user ID."""
    return 12345


@pytest.fixture
def another_user_id() -> int:
    """Another test user ID."""
    return 67890
