"""Product service with caching layer over Google Sheets."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..sheets import SheetsClient

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


class ProductService:
    """Service for product operations with TTL caching."""

    def __init__(self, sheets_client: SheetsClient):
        self._sheets = sheets_client
        self._products_cache: list[dict[str, Any]] = []
        self._products_cache_time: float = 0
        self._settings_cache: dict[str, Any] = {}
        self._settings_cache_time: float = 0
        self._categories_cache: list[str] = []
        self._categories_cache_time: float = 0

    def get_products(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get products with caching."""
        now = time.time()
        if force_refresh or (now - self._products_cache_time > CACHE_TTL_SECONDS):
            logger.debug("Refreshing products cache")
            self._products_cache = self._sheets.get_products()
            self._products_cache_time = now
        return self._products_cache

    def get_available_products(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get only in-stock products with price > 0."""
        products = self.get_products(force_refresh)
        return [p for p in products if p["stock"] > 0 and p["price_rub"] > 0]

    def get_products_by_sku(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """Get products as a dict keyed by SKU."""
        return {p["sku"]: p for p in self.get_products(force_refresh)}

    def get_product(self, sku: str) -> dict[str, Any] | None:
        """Get single product by SKU."""
        products_by_sku = self.get_products_by_sku()
        return products_by_sku.get(sku)

    def get_settings(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get settings with caching."""
        now = time.time()
        if force_refresh or (now - self._settings_cache_time > CACHE_TTL_SECONDS):
            logger.debug("Refreshing settings cache")
            self._settings_cache = self._sheets.get_settings()
            self._settings_cache_time = now
        return self._settings_cache

    def get_min_order_sum(self) -> int:
        """Get minimum order sum from settings."""
        settings = self.get_settings()
        return int(float(settings.get("Мин. сумма заказа", 5000)))

    def get_categories(self, force_refresh: bool = False) -> list[str]:
        """Get categories with caching."""
        now = time.time()
        if force_refresh or (now - self._categories_cache_time > CACHE_TTL_SECONDS):
            logger.debug("Refreshing categories cache")
            self._categories_cache = self._sheets.get_categories()
            self._categories_cache_time = now
        return self._categories_cache

    def filter_by_category(self, category: str) -> list[dict[str, Any]]:
        """Filter available products by category tag."""
        products = self.get_available_products()
        if category == "all":
            return products
        return [p for p in products if category.lower() in p.get("tags", "").lower()]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search products by name, tags, description, SKU."""
        query = query.strip().lower()
        if not query:
            return []

        products = self.get_products()
        found = []
        for p in products:
            hay = (
                p["name"] + " " + p.get("tags", "") + " " + p.get("desc_short", "") + " " + p["sku"]
            ).lower()
            if query in hay:
                found.append(p)
        return found

    def invalidate_cache(self) -> None:
        """Force cache invalidation."""
        self._products_cache_time = 0
        self._settings_cache_time = 0
        self._categories_cache_time = 0
