"""Product management service."""

import logging
import time
from dataclasses import dataclass

from app.models import Product
from app.sheets import sheets_client

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
CACHE_TTL_SECONDS = 300


@dataclass
class ProductSearchResult:
    """Result of product search."""

    products: list[Product]
    total_found: int
    query: str


class ProductCache:
    """Simple TTL cache for products."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self._cache: list[Product] | None = None
        self._cached_at: float = 0
        self._ttl = ttl_seconds

    def get(self) -> list[Product] | None:
        """Get cached products if not expired."""
        if self._cache and time.time() - self._cached_at < self._ttl:
            return self._cache
        return None

    def set(self, products: list[Product]) -> None:
        """Cache products."""
        self._cache = products
        self._cached_at = time.time()
        logger.debug(
            "product_cache_updated",
            extra={"count": len(products)},
        )

    def invalidate(self) -> None:
        """Invalidate cache."""
        self._cache = None
        self._cached_at = 0
        logger.debug("product_cache_invalidated")


class ProductService:
    """Service for product operations.

    Includes TTL-based caching for product list to reduce Google Sheets API calls.
    """

    def __init__(self):
        self._cache = ProductCache()

    async def search(self, query: str, limit: int = 5) -> ProductSearchResult:
        """Search products by SKU or name."""
        products = await sheets_client.search_products(query, limit=limit)
        return ProductSearchResult(
            products=products,
            total_found=len(products),
            query=query,
        )

    async def get_by_sku(self, sku: str) -> Product | None:
        """Get product by exact SKU."""
        return await sheets_client.find_product_by_sku(sku)

    async def get_all(self, use_cache: bool = True) -> list[Product]:
        """Get all products.

        Args:
            use_cache: If True, return cached products if available.
        """
        if use_cache:
            cached = self._cache.get()
            if cached is not None:
                logger.debug(
                    "product_cache_hit",
                    extra={"count": len(cached)},
                )
                return cached

        products = await sheets_client.get_all_products()
        self._cache.set(products)
        return products

    def invalidate_cache(self) -> None:
        """Invalidate the product cache."""
        self._cache.invalidate()

    async def update_stock(
        self,
        product: Product,
        quantity_delta: int,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product stock."""
        result = await sheets_client.update_product_stock(
            product=product,
            quantity_delta=quantity_delta,
            updated_by=updated_by,
        )
        self._cache.invalidate()
        return result

    async def update_photo(
        self,
        product: Product,
        photo_url: str,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product photo URL."""
        result = await sheets_client.update_product_photo(
            product=product,
            photo_url=photo_url,
            updated_by=updated_by,
        )
        self._cache.invalidate()
        return result

    async def toggle_active(
        self,
        product: Product,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Toggle product active status."""
        result = await sheets_client.update_product_active(
            product=product,
            active=not product.active,
            updated_by=updated_by,
        )
        self._cache.invalidate()
        return result

    async def create(
        self,
        name: str,
        price: float,
        quantity: int,
        photo_url: str = "",
        description: str = "",
        tags: str = "",
        updated_by: str = "owner_bot",
    ) -> Product:
        """Create new product."""
        result = await sheets_client.create_product(
            name=name,
            price=price,
            quantity=quantity,
            photo_url=photo_url,
            description=description,
            tags=tags,
            updated_by=updated_by,
        )
        self._cache.invalidate()
        return result

    def format_product_card(self, product: Product, show_service_fields: bool = False) -> str:
        """Format product as a card message."""
        status = "✅ Активен" if product.active else "❌ Неактивен"

        lines = [
            f"**{product.name}**",
            f"SKU: `{product.sku}`",
            f"💰 Цена: {product.price:.2f} ₽",
            f"📦 Остаток: {product.stock} шт.",
            f"Статус: {status}",
        ]

        if product.tags:
            lines.append(f"🏷️ Теги: {product.tags}")

        if product.description:
            lines.append(f"📝 {product.description}")

        if show_service_fields:
            if product.last_intake_at:
                lines.append(f"📥 Последний приход: {product.last_intake_at.strftime('%d.%m.%Y %H:%M')}")
            if product.last_intake_qty:
                lines.append(f"   Количество: +{product.last_intake_qty}")
            if product.last_updated_by:
                lines.append(f"👤 Обновлено: {product.last_updated_by}")

        return "\n".join(lines)

    def format_stock_preview(
        self,
        product: Product,
        quantity_delta: int,
    ) -> str:
        """Format stock change preview."""
        new_stock = product.stock + quantity_delta
        return (
            f"📦 **{product.name}**\n"
            f"Остаток: {product.stock} → **{new_stock}** (+{quantity_delta})"
        )


# Global service instance
product_service = ProductService()
