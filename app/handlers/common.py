"""Common utilities for handlers."""

from __future__ import annotations

from typing import Any

from ..utils import escape_html


def format_product(p: dict[str, Any], compact: bool = False) -> str:
    """
    Format product for display using HTML.
    compact=True for catalog list, False for detail.
    """
    stock = p["stock"]
    stock_emoji = "✅" if stock > 5 else ("⚠️" if stock > 0 else "❌")
    name = escape_html(p["name"])
    sku = escape_html(p["sku"])

    if compact:
        return (
            f"🏷 <b>{name}</b>\n"
            f"💰 {p['price_rub']:,} ₽ • {stock_emoji} {stock} шт.\n"
            f"📦 <code>{sku}</code>"
        )
    else:
        desc = escape_html(p.get("desc_short", ""))
        tags = escape_html(p.get("tags", ""))
        weight = p.get("package_weight")
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"🏷 <b>{name}</b>",
            "",
            f"💰 <b>Цена:</b> {p['price_rub']:,} ₽",
            f"{stock_emoji} <b>В наличии:</b> {stock} шт.",
            f"📦 <b>Артикул:</b> <code>{sku}</code>",
        ]
        if weight:
            lines.append(f"⚖️ <b>Вес:</b> {weight} г")
        if desc:
            lines.append(f"\n📝 {desc}")
        if tags:
            lines.append(f"\n🔖 {tags}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


def format_product_card(product: dict[str, Any]) -> str:
    """Format product card for catalog view using HTML."""
    stock_emoji = "✅" if product["stock"] > 5 else ("⚠️" if product["stock"] > 0 else "❌")
    name = escape_html(product["name"])
    sku = escape_html(product["sku"])
    weight = product.get("package_weight")

    caption = (
        f"🏷 <b>{name}</b>\n\n"
        f"💰 <b>Цена:</b> {product['price_rub']:,} ₽\n"
        f"{stock_emoji} <b>В наличии:</b> {product['stock']} шт.\n"
        f"📦 <b>Артикул:</b> <code>{sku}</code>"
    )

    if weight:
        caption += f"\n⚖️ <b>Вес:</b> {weight} г"

    desc = product.get("desc_short", "")
    if desc:
        caption += f"\n\n📝 <i>{escape_html(desc)}</i>"

    tags = product.get("tags", "")
    if tags:
        caption += f"\n\n🔖 {escape_html(tags)}"

    return caption
