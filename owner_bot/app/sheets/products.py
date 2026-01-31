"""Product operations for Google Sheets."""

import logging
import secrets
from datetime import datetime

from ..config import get_settings
from ..models import Product
from .cache import TTLCache
from .client import BaseSheetsClient

logger = logging.getLogger(__name__)

# Module-level cache for products (5 min TTL)
_products_cache: TTLCache[list[Product]] = TTLCache(ttl_seconds=300)


class ProductOperationsMixin:
    """Mixin for product CRUD operations."""

    async def get_all_products(
        self: BaseSheetsClient, use_cache: bool = True
    ) -> list[Product]:
        """Get all products from the sheet.

        Args:
            use_cache: If True, return cached products if available (default True).
                       Set to False to force refresh from Google Sheets.
        """
        # Check cache first
        if use_cache:
            cached = _products_cache.get()
            if cached is not None:
                logger.debug(
                    "Returning %d products from cache (age: %.1fs)",
                    len(cached),
                    _products_cache.age_seconds,
                )
                return cached

        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!A2:Z",
            )
            .execute()
        )

        rows = result.get("values", [])
        products = []

        for idx, row in enumerate(rows):
            row_data = self._row_to_dict(row)
            if row_data.get("SKU"):
                products.append(Product.from_row(idx + 2, row_data, self._col_map))

        # Update cache
        _products_cache.set(products)
        logger.debug("Cached %d products from Google Sheets", len(products))

        return products

    def invalidate_products_cache(self: BaseSheetsClient) -> None:
        """Invalidate the products cache. Call after create/update/delete."""
        _products_cache.invalidate()
        logger.debug("Products cache invalidated")

    async def find_product_by_sku(self: BaseSheetsClient, sku: str) -> Product | None:
        """Find product by exact SKU match."""
        products = await self.get_all_products()
        for product in products:
            if product.sku == sku:
                return product
        return None

    async def search_products(
        self: BaseSheetsClient, query: str, limit: int = 5
    ) -> list[Product]:
        """Search products by name (contains) or SKU (exact)."""
        products = await self.get_all_products()
        query_lower = query.lower()

        for product in products:
            if product.sku.lower() == query_lower:
                return [product]

        matches = [p for p in products if query_lower in p.name.lower()]
        return matches[:limit]

    def _generate_sku(self: BaseSheetsClient) -> str:
        """Generate unique SKU in format PRD-YYYYMMDD-XXXX."""
        date_part = datetime.now().strftime("%Y%m%d")
        random_part = secrets.token_hex(2).upper()
        return f"PRD-{date_part}-{random_part}"

    async def create_product(
        self: BaseSheetsClient,
        name: str,
        price: float,
        quantity: int,
        photo_url: str = "",
        description: str = "",
        tags: str = "",
        updated_by: str = "owner_bot",
    ) -> Product:
        """Create a new product in the sheet."""
        settings = get_settings()
        sku = self._generate_sku()
        now = datetime.now().isoformat()

        logger.info(
            "create_product: sku=%s, name=%s, price=%s, qty=%s", sku, name, price, quantity
        )

        row = [""] * (max(self._col_map.values()) + 1)

        row[self._col_idx("SKU")] = sku
        row[self._col_idx("Наименование")] = name
        row[self._col_idx("Цена")] = price
        row[self._col_idx("Остаток")] = quantity
        row[self._col_idx("Фото")] = photo_url
        row[self._col_idx("Активен")] = "TRUE"

        if "Теги" in self._col_map:
            row[self._col_map["Теги"]] = tags
        if "Описание_кратко" in self._col_map:
            row[self._col_map["Описание_кратко"]] = description
        if "last_intake_at" in self._col_map:
            row[self._col_map["last_intake_at"]] = now
        if "last_intake_qty" in self._col_map:
            row[self._col_map["last_intake_qty"]] = quantity
        if "last_updated_by" in self._col_map:
            row[self._col_map["last_updated_by"]] = updated_by

        logger.info("create_product: appending row to sheet %s", self._sheet_name)

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!A:A",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )

        logger.info("create_product: append result=%s", result)

        updated_range = result.get("updates", {}).get("updatedRange", "")
        row_num = int(updated_range.split("!")[1].split(":")[0][1:])
        logger.info("create_product: new row_num=%d", row_num)

        # Invalidate cache after creating product
        self.invalidate_products_cache()

        return Product(
            row_number=row_num,
            sku=sku,
            name=name,
            price=price,
            stock=quantity,
            photo_url=photo_url,
            description=description,
            tags=tags,
            active=True,
            last_intake_at=datetime.now(),
            last_intake_qty=quantity,
            last_updated_by=updated_by,
        )

    async def update_product_stock(
        self: BaseSheetsClient,
        product: Product,
        quantity_delta: int,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product stock by adding quantity_delta."""
        settings = get_settings()
        new_stock = product.stock + quantity_delta
        now = datetime.now().isoformat()

        logger.info(
            "update_product_stock: SKU=%s, row=%d, old=%d, delta=%d, new=%d",
            product.sku,
            product.row_number,
            product.stock,
            quantity_delta,
            new_stock,
        )

        updates = []

        stock_col = self._col_letter(self._col_idx("Остаток"))
        updates.append(
            {
                "range": f"{self._sheet_name}!{stock_col}{product.row_number}",
                "values": [[new_stock]],
            }
        )

        if "last_intake_at" in self._col_map:
            col = self._col_letter(self._col_map["last_intake_at"])
            updates.append(
                {
                    "range": f"{self._sheet_name}!{col}{product.row_number}",
                    "values": [[now]],
                }
            )

        if "last_intake_qty" in self._col_map:
            col = self._col_letter(self._col_map["last_intake_qty"])
            updates.append(
                {
                    "range": f"{self._sheet_name}!{col}{product.row_number}",
                    "values": [[quantity_delta]],
                }
            )

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append(
                {
                    "range": f"{self._sheet_name}!{col}{product.row_number}",
                    "values": [[updated_by]],
                }
            )

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        # Invalidate cache after updating stock
        self.invalidate_products_cache()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=new_stock,
            photo_url=product.photo_url,
            description=product.description,
            tags=product.tags,
            active=product.active,
            last_intake_at=datetime.now(),
            last_intake_qty=quantity_delta,
            last_updated_by=updated_by,
        )

    async def update_product_photo(
        self: BaseSheetsClient,
        product: Product,
        photo_url: str,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product photo URL."""
        settings = get_settings()

        photo_col = self._col_letter(self._col_idx("Фото"))
        updates = [
            {
                "range": f"{self._sheet_name}!{photo_col}{product.row_number}",
                "values": [[photo_url]],
            }
        ]

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append(
                {
                    "range": f"{self._sheet_name}!{col}{product.row_number}",
                    "values": [[updated_by]],
                }
            )

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        # Invalidate cache after updating photo
        self.invalidate_products_cache()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=product.stock,
            photo_url=photo_url,
            description=product.description,
            tags=product.tags,
            active=product.active,
            last_intake_at=product.last_intake_at,
            last_intake_qty=product.last_intake_qty,
            last_updated_by=updated_by,
        )

    async def update_product_active(
        self: BaseSheetsClient,
        product: Product,
        active: bool,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product active status."""
        settings = get_settings()

        active_col = self._col_letter(self._col_map["Активен"])
        updates = [
            {
                "range": f"{self._sheet_name}!{active_col}{product.row_number}",
                "values": [["TRUE" if active else "FALSE"]],
            }
        ]

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append(
                {
                    "range": f"{self._sheet_name}!{col}{product.row_number}",
                    "values": [[updated_by]],
                }
            )

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        # Invalidate cache after updating active status
        self.invalidate_products_cache()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=product.stock,
            photo_url=product.photo_url,
            description=product.description,
            tags=product.tags,
            active=active,
            last_intake_at=product.last_intake_at,
            last_intake_qty=product.last_intake_qty,
            last_updated_by=updated_by,
        )

    async def get_product_by_row(
        self: BaseSheetsClient, row_number: int
    ) -> Product | None:
        """Get product by row number."""
        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!A{row_number}:Z{row_number}",
            )
            .execute()
        )

        rows = result.get("values", [])
        if not rows or not rows[0]:
            return None

        row_data = self._row_to_dict(rows[0])
        if not row_data.get("SKU"):
            return None

        return Product.from_row(row_number, row_data, self._col_map)
