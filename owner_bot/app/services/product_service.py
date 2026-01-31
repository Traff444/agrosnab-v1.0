"""Product management service."""

from dataclasses import dataclass

from app.models import Product
from app.sheets import sheets_client


@dataclass
class ProductSearchResult:
    """Result of product search."""

    products: list[Product]
    total_found: int
    query: str


class ProductService:
    """Service for product operations."""

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

    async def get_all(self) -> list[Product]:
        """Get all products."""
        return await sheets_client.get_all_products()

    async def update_stock(
        self,
        product: Product,
        quantity_delta: int,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product stock."""
        return await sheets_client.update_product_stock(
            product=product,
            quantity_delta=quantity_delta,
            updated_by=updated_by,
        )

    async def update_photo(
        self,
        product: Product,
        photo_url: str,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product photo URL."""
        return await sheets_client.update_product_photo(
            product=product,
            photo_url=photo_url,
            updated_by=updated_by,
        )

    async def toggle_active(
        self,
        product: Product,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Toggle product active status."""
        return await sheets_client.update_product_active(
            product=product,
            active=not product.active,
            updated_by=updated_by,
        )

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
        return await sheets_client.create_product(
            name=name,
            price=price,
            quantity=quantity,
            photo_url=photo_url,
            description=description,
            tags=tags,
            updated_by=updated_by,
        )

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
