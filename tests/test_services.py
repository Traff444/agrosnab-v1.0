"""Tests for service layer."""

import sys
from unittest.mock import MagicMock

import pytest

# Mock google modules before importing app modules
sys.modules["google"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.service_account"] = MagicMock()
googleapiclient_mock = MagicMock()
sys.modules["googleapiclient"] = googleapiclient_mock
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["googleapiclient.errors"] = MagicMock()


class MockSheetsClient:
    """Mock Google Sheets client."""

    def __init__(self, products=None, settings=None):
        self._products = products or []
        self._settings = settings or {}

    def get_products(self):
        return self._products

    def get_settings(self):
        return self._settings

    def get_categories(self):
        tags_set = set()
        for p in self._products:
            tags = p.get("tags", "")
            if tags:
                for tag in tags.split(","):
                    tag = tag.strip()
                    if tag:
                        tags_set.add(tag)
        return sorted(tags_set)


@pytest.fixture
def sample_products():
    return [
        {
            "sku": "PRD-001",
            "name": "Махорка Золотая",
            "desc_short": "Премиум сорт",
            "price_rub": 1000,
            "stock": 100,
            "tags": "табак,премиум",
            "photo_url": "",
        },
        {
            "sku": "PRD-002",
            "name": "Махорка СССР",
            "desc_short": "Классика",
            "price_rub": 500,
            "stock": 50,
            "tags": "табак,классика",
            "photo_url": "",
        },
        {
            "sku": "PRD-003",
            "name": "Трубка курительная",
            "desc_short": "Деревянная",
            "price_rub": 2000,
            "stock": 0,  # Out of stock
            "tags": "аксессуары",
            "photo_url": "",
        },
    ]


@pytest.fixture
def sample_settings():
    return {
        "Мин. сумма заказа": "5000",
        "Компания": "ООО Тест",
    }


class TestProductService:
    """Tests for ProductService."""

    def test_get_products_caching(self, sample_products):
        """Test that products are cached."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        # First call - should fetch from sheets
        products1 = service.get_products()
        assert len(products1) == 3

        # Modify mock data
        mock_sheets._products = []

        # Second call within TTL - should return cached
        products2 = service.get_products()
        assert len(products2) == 3  # Still returns cached data

    def test_get_products_force_refresh(self, sample_products):
        """Test force refresh bypasses cache."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        products1 = service.get_products()
        assert len(products1) == 3

        # Modify mock data
        mock_sheets._products = sample_products[:1]

        # Force refresh
        products2 = service.get_products(force_refresh=True)
        assert len(products2) == 1

    def test_get_available_products(self, sample_products):
        """Test filtering to only available products."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        available = service.get_available_products()
        assert len(available) == 2  # PRD-003 is out of stock
        assert all(p["stock"] > 0 for p in available)

    def test_get_product_by_sku(self, sample_products):
        """Test getting single product by SKU."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        product = service.get_product("PRD-001")
        assert product["name"] == "Махорка Золотая"

        # Non-existent SKU
        assert service.get_product("NON-EXISTENT") is None

    def test_get_min_order_sum(self, sample_products, sample_settings):
        """Test getting minimum order sum."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products, settings=sample_settings)
        service = ProductService(mock_sheets)

        assert service.get_min_order_sum() == 5000

    def test_filter_by_category(self, sample_products):
        """Test filtering products by category."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        # Filter by "премиум"
        premium = service.filter_by_category("премиум")
        assert len(premium) == 1
        assert premium[0]["sku"] == "PRD-001"

        # "all" should return all available
        all_products = service.filter_by_category("all")
        assert len(all_products) == 2

    def test_search(self, sample_products):
        """Test product search."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        # Search by name
        results = service.search("золотая")
        assert len(results) == 1
        assert results[0]["sku"] == "PRD-001"

        # Search by tag
        results = service.search("классика")
        assert len(results) == 1
        assert results[0]["sku"] == "PRD-002"

        # Search by SKU
        results = service.search("PRD-003")
        assert len(results) == 1

        # Empty search
        results = service.search("")
        assert len(results) == 0

    def test_invalidate_cache(self, sample_products):
        """Test cache invalidation."""
        from app.services.product_service import ProductService

        mock_sheets = MockSheetsClient(products=sample_products)
        service = ProductService(mock_sheets)

        # Populate cache
        service.get_products()

        # Modify mock
        mock_sheets._products = []

        # Without invalidation - returns cached
        assert len(service.get_products()) == 3

        # Invalidate
        service.invalidate_cache()

        # Now returns new data
        assert len(service.get_products()) == 0


class TestCartService:
    """Tests for CartService."""

    @pytest.mark.asyncio
    async def test_add_to_cart_validation(self, sample_products, monkeypatch, tmp_path):
        """Test cart validation when adding items."""
        from app import cart_store
        from app.services.cart_service import CartService
        from app.services.product_service import ProductService

        # Setup temp DB
        db_path = str(tmp_path / "test.sqlite3")
        monkeypatch.setattr(cart_store, "DB_PATH", db_path)
        await cart_store.init_db()

        mock_sheets = MockSheetsClient(products=sample_products)
        product_service = ProductService(mock_sheets)
        cart_service = CartService(product_service)

        user_id = 123

        # Add valid item
        success, msg = await cart_service.add_to_cart(user_id, "PRD-001", 5)
        assert success is True
        assert "добавлено" in msg

        # Add non-existent SKU
        success, msg = await cart_service.add_to_cart(user_id, "INVALID", 1)
        assert success is False
        assert "не найден" in msg

        # Add out of stock item
        success, msg = await cart_service.add_to_cart(user_id, "PRD-003", 1)
        assert success is False
        assert "закончился" in msg

    @pytest.mark.asyncio
    async def test_add_to_cart_stock_limit(self, sample_products, monkeypatch, tmp_path):
        """Test that cart respects stock limits."""
        from app import cart_store
        from app.services.cart_service import CartService
        from app.services.product_service import ProductService

        db_path = str(tmp_path / "test.sqlite3")
        monkeypatch.setattr(cart_store, "DB_PATH", db_path)
        await cart_store.init_db()

        mock_sheets = MockSheetsClient(products=sample_products)
        product_service = ProductService(mock_sheets)
        cart_service = CartService(product_service)

        user_id = 123

        # PRD-002 has 50 stock
        success, _ = await cart_service.add_to_cart(user_id, "PRD-002", 45)
        assert success is True

        # Try to add more than stock
        success, msg = await cart_service.add_to_cart(user_id, "PRD-002", 10)
        assert success is False
        assert "остаток" in msg.lower() or "можно добавить" in msg.lower()

    @pytest.mark.asyncio
    async def test_cart_summary(self, sample_products, sample_settings, monkeypatch, tmp_path):
        """Test cart summary calculation."""
        from app import cart_store
        from app.services.cart_service import CartService
        from app.services.product_service import ProductService

        db_path = str(tmp_path / "test.sqlite3")
        monkeypatch.setattr(cart_store, "DB_PATH", db_path)
        await cart_store.init_db()

        mock_sheets = MockSheetsClient(products=sample_products, settings=sample_settings)
        product_service = ProductService(mock_sheets)
        cart_service = CartService(product_service)

        user_id = 123

        # Empty cart
        summary = await cart_service.get_cart_summary(user_id)
        assert summary.is_empty is True
        assert summary.total == 0
        assert summary.below_min is True

        # Add items
        await cart_service.add_to_cart(user_id, "PRD-001", 3)  # 3000 руб
        await cart_service.add_to_cart(user_id, "PRD-002", 4)  # 2000 руб

        summary = await cart_service.get_cart_summary(user_id)
        assert summary.is_empty is False
        assert summary.total == 5000
        assert len(summary.items) == 2
        assert summary.below_min is False  # 5000 = min

    @pytest.mark.asyncio
    async def test_format_cart_text(self, sample_products, sample_settings, monkeypatch, tmp_path):
        """Test cart text formatting."""
        from app import cart_store
        from app.services.cart_service import CartService
        from app.services.product_service import ProductService

        db_path = str(tmp_path / "test.sqlite3")
        monkeypatch.setattr(cart_store, "DB_PATH", db_path)
        await cart_store.init_db()

        mock_sheets = MockSheetsClient(products=sample_products, settings=sample_settings)
        product_service = ProductService(mock_sheets)
        cart_service = CartService(product_service)

        user_id = 123

        # Empty cart
        summary = await cart_service.get_cart_summary(user_id)
        text = cart_service.format_cart_text(summary)
        assert "Пока пусто" in text

        # With items
        await cart_service.add_to_cart(user_id, "PRD-001", 2)
        summary = await cart_service.get_cart_summary(user_id)
        text = cart_service.format_cart_text(summary)

        assert "Корзина" in text
        assert "Махорка Золотая" in text
        assert "2 000" in text or "2,000" in text  # Price formatting
