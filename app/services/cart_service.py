"""Cart service with business logic and formatting."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .. import cart_store
from ..keyboards import cart_kb, cart_with_items_kb
from ..utils import escape_html
from .product_service import ProductService

logger = logging.getLogger(__name__)


@dataclass
class CartSummary:
    """Cart summary data."""

    lines: list[str]
    total: int
    items: list[tuple[str, int, str]]  # (sku, qty, name)
    is_empty: bool
    min_sum: int
    below_min: bool


class CartService:
    """Service for cart operations."""

    def __init__(self, product_service: ProductService):
        self._products = product_service

    async def get_cart_summary(self, user_id: int) -> CartSummary:
        """Get cart summary with formatted lines and total."""
        cart_items = await cart_store.get_cart(user_id)
        products_by_sku = self._products.get_products_by_sku()
        min_sum = self._products.get_min_order_sum()

        if not cart_items:
            return CartSummary(
                lines=[],
                total=0,
                items=[],
                is_empty=True,
                min_sum=min_sum,
                below_min=True,
            )

        lines = []
        total = 0
        items = []

        for sku, qty in cart_items:
            p = products_by_sku.get(sku)
            if not p:
                continue
            line_sum = qty * p["price_rub"]
            total += line_sum
            name = escape_html(p["name"])
            lines.append(f"• <b>{name}</b>\n  {qty} × {p['price_rub']:,} ₽ = <b>{line_sum:,} ₽</b>")
            items.append((sku, qty, p["name"]))

        return CartSummary(
            lines=lines,
            total=total,
            items=items,
            is_empty=len(items) == 0,
            min_sum=min_sum,
            below_min=total < min_sum,
        )

    def format_cart_text(self, summary: CartSummary) -> str:
        """Format cart for display using HTML."""
        if summary.is_empty:
            return "🧰 <b>Корзина</b>\n\nПока пусто. Добавьте товары из каталога!"

        text = "🧰 <b>Корзина</b>\n\n" + "\n\n".join(summary.lines)
        text += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n💰 <b>Итого: {summary.total:,} ₽</b>"

        if summary.below_min:
            text += f"\n⚠️ Минималка: {summary.min_sum:,} ₽"

        return text

    def get_cart_keyboard(self, summary: CartSummary):
        """Get appropriate keyboard for cart state."""
        if summary.is_empty:
            return cart_kb()
        return cart_with_items_kb(summary.items)

    async def add_to_cart(
        self,
        user_id: int,
        sku: str,
        qty: int,
    ) -> tuple[bool, str]:
        """
        Add item to cart with validation.
        Returns (success, message).
        """
        product = self._products.get_product(sku)

        if not product:
            logger.warning("add_nonexistent_sku", extra={"sku": sku})
            return False, f"Товар с артикулом {sku} не найден"

        if product["stock"] <= 0:
            return False, f"Товар «{product['name']}» закончился на складе"

        # Check current cart qty + new qty doesn't exceed stock
        cart_items = await cart_store.get_cart(user_id)
        current_qty = next((q for s, q in cart_items if s == sku), 0)

        if current_qty + qty > product["stock"]:
            available = product["stock"] - current_qty
            if available <= 0:
                return False, f"Максимум {product['stock']} шт. уже в корзине"
            return False, f"Можно добавить ещё {available} шт. (остаток: {product['stock']})"

        await cart_store.add_to_cart(user_id, sku, qty)

        # Get updated cart info
        cart_items = await cart_store.get_cart(user_id)
        total_items = sum(q for _, q in cart_items)

        return True, f"✅ {product['name']} × {qty} добавлено!\n🧺 В корзине: {total_items} шт."

    async def calc_cart_for_checkout(
        self,
        user_id: int,
    ) -> tuple[list[str], int, list[tuple[str, int]]]:
        """Calculate cart for checkout. Returns (lines, total, items)."""
        cart_items = await cart_store.get_cart(user_id)
        products_by_sku = self._products.get_products_by_sku()

        lines = []
        total = 0
        for sku, qty in cart_items:
            p = products_by_sku.get(sku)
            if not p:
                continue
            line_sum = qty * p["price_rub"]
            total += line_sum
            lines.append(f"- {p['name']} ({sku}) × {qty} = {line_sum} ₽")

        return lines, total, cart_items
