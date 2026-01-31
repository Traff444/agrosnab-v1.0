"""Pytest configuration."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """
    Isolate each test with its own database.

    This fixture patches DB_PATH in all storage modules to use
    a unique temporary database for each test.
    """
    test_db_path = str(tmp_path / "test_isolated.sqlite3")

    # Patch DB_PATH in all storage modules that use it
    monkeypatch.setattr("app.storage.db.DB_PATH", test_db_path)
    monkeypatch.setattr("app.storage.cart.DB_PATH", test_db_path)
    monkeypatch.setattr("app.storage.crm.DB_PATH", test_db_path)
    monkeypatch.setattr("app.storage.chat_history.DB_PATH", test_db_path)

    # Also patch in cart_store for backward compatibility
    try:
        monkeypatch.setattr("app.cart_store.DB_PATH", test_db_path)
    except AttributeError:
        pass  # cart_store may not be imported yet

    yield test_db_path
