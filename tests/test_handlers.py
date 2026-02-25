"""Tests for handler utilities and navigation callbacks."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers: product fixtures
# ---------------------------------------------------------------------------


def _make_product(**overrides: Any) -> dict[str, Any]:
    """Build a product dict with sensible defaults.

    Callers can override any field via keyword arguments.
    """
    base: dict[str, Any] = {
        "name": "Махорка Премиум",
        "sku": "SKU-001",
        "price_rub": 1500,
        "stock": 10,
    }
    return {**base, **overrides}


# ===================================================================
# format_product
# ===================================================================


class TestFormatProductCompact:
    """Tests for format_product() with compact=True (catalog list view)."""

    def test_basic_compact_format(self):
        """Compact format contains name, price, stock and SKU on separate lines."""
        from app.handlers.common import format_product

        product = _make_product()
        result = format_product(product, compact=True)

        assert "<b>Махорка Премиум</b>" in result
        assert "1,500 ₽" in result
        assert "<code>SKU-001</code>" in result

    def test_compact_has_three_lines(self):
        """Compact output always has exactly three lines."""
        from app.handlers.common import format_product

        product = _make_product()
        lines = format_product(product, compact=True).split("\n")

        assert len(lines) == 3

    def test_compact_stock_high(self):
        """Stock > 5 uses the green check emoji."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=10), compact=True)

        assert "\u2705" in result  # checkmark

    def test_compact_stock_low(self):
        """Stock 1-5 uses the warning emoji."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=3), compact=True)

        assert "\u26a0\ufe0f" in result  # warning

    def test_compact_stock_zero(self):
        """Stock 0 uses the red cross emoji."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=0), compact=True)

        assert "\u274c" in result  # red cross

    def test_compact_stock_boundary_five(self):
        """Stock exactly 5 is in the low-stock range (warning emoji)."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=5), compact=True)

        assert "\u26a0\ufe0f" in result

    def test_compact_stock_boundary_six(self):
        """Stock exactly 6 is in the high-stock range (green check)."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=6), compact=True)

        assert "\u2705" in result

    def test_compact_stock_boundary_one(self):
        """Stock exactly 1 is in the low-stock range (warning emoji)."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=1), compact=True)

        assert "\u26a0\ufe0f" in result

    def test_compact_ignores_description(self):
        """Compact format does not include description."""
        from app.handlers.common import format_product

        product = _make_product(desc_short="Some description here")
        result = format_product(product, compact=True)

        assert "Some description here" not in result

    def test_compact_ignores_tags(self):
        """Compact format does not include tags."""
        from app.handlers.common import format_product

        product = _make_product(tags="#sale, #hit")
        result = format_product(product, compact=True)

        assert "#sale" not in result

    def test_compact_ignores_weight(self):
        """Compact format does not include weight."""
        from app.handlers.common import format_product

        product = _make_product(package_weight=250)
        result = format_product(product, compact=True)

        assert "250" not in result


class TestFormatProductFull:
    """Tests for format_product() with compact=False (detail view)."""

    def test_full_has_separator_lines(self):
        """Full format starts and ends with separator lines."""
        from app.handlers.common import format_product

        product = _make_product()
        result = format_product(product, compact=False)
        lines = result.split("\n")

        assert lines[0].startswith("\u2501")
        assert lines[-1].startswith("\u2501")

    def test_full_contains_name(self):
        """Full format includes product name in bold."""
        from app.handlers.common import format_product

        result = format_product(_make_product(), compact=False)

        assert "<b>Махорка Премиум</b>" in result

    def test_full_contains_price(self):
        """Full format includes price with label."""
        from app.handlers.common import format_product

        result = format_product(_make_product(), compact=False)

        assert "<b>Цена:</b>" in result
        assert "1,500 ₽" in result

    def test_full_contains_stock(self):
        """Full format includes stock with label."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=7), compact=False)

        assert "<b>В наличии:</b>" in result
        assert "7 шт." in result

    def test_full_contains_sku(self):
        """Full format includes SKU in code tags."""
        from app.handlers.common import format_product

        result = format_product(_make_product(), compact=False)

        assert "<b>Артикул:</b>" in result
        assert "<code>SKU-001</code>" in result

    def test_full_with_weight(self):
        """Full format includes weight when provided."""
        from app.handlers.common import format_product

        product = _make_product(package_weight=250)
        result = format_product(product, compact=False)

        assert "<b>Вес:</b>" in result
        assert "250 г" in result

    def test_full_without_weight(self):
        """Full format omits weight line when not provided."""
        from app.handlers.common import format_product

        result = format_product(_make_product(), compact=False)

        assert "Вес:" not in result

    def test_full_with_zero_weight(self):
        """Full format omits weight line when weight is 0 (falsy)."""
        from app.handlers.common import format_product

        product = _make_product(package_weight=0)
        result = format_product(product, compact=False)

        assert "Вес:" not in result

    def test_full_with_description(self):
        """Full format includes description when provided."""
        from app.handlers.common import format_product

        product = _make_product(desc_short="Натуральная махорка высшего сорта")
        result = format_product(product, compact=False)

        assert "Натуральная махорка высшего сорта" in result

    def test_full_without_description(self):
        """Full format omits description section when empty."""
        from app.handlers.common import format_product

        product = _make_product(desc_short="")
        result = format_product(product, compact=False)

        # The note emoji for description should not appear without text
        lines = result.split("\n")
        desc_lines = [l for l in lines if l.strip().startswith("\U0001f4dd")]
        assert len(desc_lines) == 0

    def test_full_without_description_key(self):
        """Full format handles missing desc_short key gracefully."""
        from app.handlers.common import format_product

        product = _make_product()
        # desc_short is not in the product dict at all
        result = format_product(product, compact=False)

        assert "Вес:" not in result or True  # just verify no crash

    def test_full_with_tags(self):
        """Full format includes tags when provided."""
        from app.handlers.common import format_product

        product = _make_product(tags="#sale, #new")
        result = format_product(product, compact=False)

        assert "#sale, #new" in result

    def test_full_without_tags(self):
        """Full format omits tags section when empty."""
        from app.handlers.common import format_product

        product = _make_product(tags="")
        result = format_product(product, compact=False)

        lines = result.split("\n")
        tag_lines = [l for l in lines if l.strip().startswith("\U0001f516")]
        assert len(tag_lines) == 0

    def test_full_stock_high(self):
        """Full detail view shows green check for stock > 5."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=20), compact=False)

        assert "\u2705" in result

    def test_full_stock_low(self):
        """Full detail view shows warning for stock 1-5."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=2), compact=False)

        assert "\u26a0\ufe0f" in result

    def test_full_stock_zero(self):
        """Full detail view shows red cross for stock 0."""
        from app.handlers.common import format_product

        result = format_product(_make_product(stock=0), compact=False)

        assert "\u274c" in result

    def test_full_default_is_not_compact(self):
        """Calling format_product without compact defaults to full format."""
        from app.handlers.common import format_product

        result = format_product(_make_product())
        lines = result.split("\n")

        # Full format has separator lines; compact does not
        assert lines[0].startswith("\u2501")


class TestFormatProductHtmlEscaping:
    """Tests for HTML escaping in format_product()."""

    def test_name_with_angle_brackets_is_escaped(self):
        """Product names containing < and > are HTML-escaped."""
        from app.handlers.common import format_product

        product = _make_product(name="Товар <Специальный>")
        result = format_product(product, compact=True)

        assert "&lt;Специальный&gt;" in result
        assert "<Специальный>" not in result

    def test_name_with_ampersand_is_escaped(self):
        """Product names containing & are HTML-escaped."""
        from app.handlers.common import format_product

        product = _make_product(name="Табак & Махорка")
        result = format_product(product, compact=True)

        assert "&amp;" in result

    def test_sku_with_special_chars_is_escaped(self):
        """SKU containing HTML special chars is escaped."""
        from app.handlers.common import format_product

        product = _make_product(sku="SKU<01>&02")
        result = format_product(product, compact=True)

        assert "SKU&lt;01&gt;&amp;02" in result

    def test_full_description_is_escaped(self):
        """Description text in full format is HTML-escaped."""
        from app.handlers.common import format_product

        product = _make_product(desc_short="<script>alert('xss')</script>")
        result = format_product(product, compact=False)

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_full_tags_are_escaped(self):
        """Tags in full format are HTML-escaped."""
        from app.handlers.common import format_product

        product = _make_product(tags="<b>bold</b>")
        result = format_product(product, compact=False)

        # The escape_html should escape the user-provided <b> tags
        assert "&lt;b&gt;" in result

    def test_compact_name_with_quotes_is_escaped(self):
        """Product names with double quotes are HTML-escaped."""
        from app.handlers.common import format_product

        product = _make_product(name='Махорка "Особая"')
        result = format_product(product, compact=True)

        # html.escape converts " to &quot;
        assert "&quot;" in result


class TestFormatProductPriceFormatting:
    """Tests for price formatting with thousand separators."""

    def test_price_with_comma_separator(self):
        """Price uses comma as thousand separator per Python format spec."""
        from app.handlers.common import format_product

        product = _make_product(price_rub=15000)
        result = format_product(product, compact=True)

        assert "15,000" in result

    def test_small_price_no_separator(self):
        """Price below 1000 has no separator."""
        from app.handlers.common import format_product

        product = _make_product(price_rub=500)
        result = format_product(product, compact=True)

        assert "500 \u20bd" in result

    def test_large_price(self):
        """Very large price is formatted correctly."""
        from app.handlers.common import format_product

        product = _make_product(price_rub=1_500_000)
        result = format_product(product, compact=True)

        assert "1,500,000" in result


# ===================================================================
# format_product_card
# ===================================================================


class TestFormatProductCard:
    """Tests for format_product_card() function (catalog card view)."""

    def test_basic_card_format(self):
        """Card contains name, price, stock and SKU."""
        from app.handlers.common import format_product_card

        product = _make_product()
        result = format_product_card(product)

        assert "<b>Махорка Премиум</b>" in result
        assert "1,500 ₽" in result
        assert "<code>SKU-001</code>" in result
        assert "шт." in result

    def test_card_stock_high(self):
        """Card shows green check for stock > 5."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product(stock=10))

        assert "\u2705" in result

    def test_card_stock_low(self):
        """Card shows warning for stock 1-5."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product(stock=4))

        assert "\u26a0\ufe0f" in result

    def test_card_stock_zero(self):
        """Card shows red cross for stock 0."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product(stock=0))

        assert "\u274c" in result

    def test_card_stock_boundary_five(self):
        """Stock exactly 5 uses warning emoji in card."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product(stock=5))

        assert "\u26a0\ufe0f" in result

    def test_card_stock_boundary_six(self):
        """Stock exactly 6 uses green check emoji in card."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product(stock=6))

        assert "\u2705" in result

    def test_card_with_weight(self):
        """Card includes weight when present."""
        from app.handlers.common import format_product_card

        product = _make_product(package_weight=500)
        result = format_product_card(product)

        assert "<b>Вес:</b>" in result
        assert "500 г" in result

    def test_card_without_weight(self):
        """Card omits weight when not present."""
        from app.handlers.common import format_product_card

        result = format_product_card(_make_product())

        assert "Вес:" not in result

    def test_card_with_zero_weight(self):
        """Card omits weight when weight is 0 (falsy)."""
        from app.handlers.common import format_product_card

        product = _make_product(package_weight=0)
        result = format_product_card(product)

        assert "Вес:" not in result

    def test_card_with_description(self):
        """Card includes italic description when present."""
        from app.handlers.common import format_product_card

        product = _make_product(desc_short="Описание товара")
        result = format_product_card(product)

        assert "<i>Описание товара</i>" in result

    def test_card_without_description(self):
        """Card omits description section when empty."""
        from app.handlers.common import format_product_card

        product = _make_product(desc_short="")
        result = format_product_card(product)

        assert "<i>" not in result

    def test_card_without_description_key(self):
        """Card handles missing desc_short key."""
        from app.handlers.common import format_product_card

        product = _make_product()
        # No desc_short key at all
        result = format_product_card(product)

        assert "<i>" not in result

    def test_card_with_tags(self):
        """Card includes tags when present."""
        from app.handlers.common import format_product_card

        product = _make_product(tags="#hit, #new")
        result = format_product_card(product)

        assert "#hit, #new" in result

    def test_card_without_tags(self):
        """Card omits tags when empty."""
        from app.handlers.common import format_product_card

        product = _make_product(tags="")
        result = format_product_card(product)

        # Tag emoji should not appear if tags are empty
        tag_occurrences = result.count("\U0001f516")
        assert tag_occurrences == 0

    def test_card_without_tags_key(self):
        """Card handles missing tags key."""
        from app.handlers.common import format_product_card

        product = _make_product()
        result = format_product_card(product)

        tag_occurrences = result.count("\U0001f516")
        assert tag_occurrences == 0

    def test_card_with_all_optional_fields(self):
        """Card with weight, description and tags includes all sections."""
        from app.handlers.common import format_product_card

        product = _make_product(
            package_weight=300,
            desc_short="Отличный товар",
            tags="#sale",
        )
        result = format_product_card(product)

        assert "300 г" in result
        assert "Отличный товар" in result
        assert "#sale" in result


class TestFormatProductCardHtmlEscaping:
    """Tests for HTML escaping in format_product_card()."""

    def test_card_name_escapes_angle_brackets(self):
        """Name with < and > is escaped in card."""
        from app.handlers.common import format_product_card

        product = _make_product(name="<b>Fake Bold</b>")
        result = format_product_card(product)

        assert "&lt;b&gt;Fake Bold&lt;/b&gt;" in result

    def test_card_name_escapes_ampersand(self):
        """Name with & is escaped in card."""
        from app.handlers.common import format_product_card

        product = _make_product(name="A & B")
        result = format_product_card(product)

        assert "A &amp; B" in result

    def test_card_sku_is_escaped(self):
        """SKU with special chars is escaped in card."""
        from app.handlers.common import format_product_card

        product = _make_product(sku="<SKU>&01")
        result = format_product_card(product)

        assert "&lt;SKU&gt;&amp;01" in result

    def test_card_description_is_escaped(self):
        """Description text in card is HTML-escaped."""
        from app.handlers.common import format_product_card

        product = _make_product(desc_short="<script>alert(1)</script>")
        result = format_product_card(product)

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_card_tags_are_escaped(self):
        """Tags in card are HTML-escaped."""
        from app.handlers.common import format_product_card

        product = _make_product(tags="<img src=x>")
        result = format_product_card(product)

        assert "<img" not in result
        assert "&lt;img" in result


# ===================================================================
# pageinfo_handler
# ===================================================================


def _make_callback_query(data: str) -> MagicMock:
    """Build a mock CallbackQuery with given data and an async answer method."""
    callback = MagicMock()
    callback.data = data
    callback.answer = AsyncMock()
    return callback


class TestPageinfoHandler:
    """Tests for pageinfo_handler() callback from navigation.py."""

    @pytest.mark.asyncio
    async def test_valid_pageinfo(self):
        """Valid 'pageinfo:2:5' data answers with page info toast."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:2:5")
        await pageinfo_handler(callback)

        callback.answer.assert_awaited_once_with("Страница 2 из 5")

    @pytest.mark.asyncio
    async def test_first_page(self):
        """Page 1 of 1 shows correct message."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:1:1")
        await pageinfo_handler(callback)

        callback.answer.assert_awaited_once_with("Страница 1 из 1")

    @pytest.mark.asyncio
    async def test_large_page_numbers(self):
        """Large page numbers are handled correctly."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:99:100")
        await pageinfo_handler(callback)

        callback.answer.assert_awaited_once_with("Страница 99 из 100")

    @pytest.mark.asyncio
    async def test_invalid_too_few_parts(self):
        """Callback data with fewer than 3 colon-separated parts returns error."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:2")
        await pageinfo_handler(callback)

        callback.answer.assert_awaited_once_with("Ошибка")

    @pytest.mark.asyncio
    async def test_invalid_only_prefix(self):
        """Callback data with only the prefix returns error."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:")
        await pageinfo_handler(callback)

        # "pageinfo:".split(":") => ["pageinfo", ""] which is 2 parts < 3
        callback.answer.assert_awaited_once_with("Ошибка")

    @pytest.mark.asyncio
    async def test_extra_parts_still_works(self):
        """Callback data with extra colon-separated parts still extracts page and total."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:3:10:extra")
        await pageinfo_handler(callback)

        # parts[1] = "3", parts[2] = "10"
        callback.answer.assert_awaited_once_with("Страница 3 из 10")

    @pytest.mark.asyncio
    async def test_non_numeric_page_values(self):
        """Non-numeric page values are passed through as strings (no crash)."""
        from app.handlers.navigation import pageinfo_handler

        callback = _make_callback_query("pageinfo:abc:xyz")
        await pageinfo_handler(callback)

        # The handler does not validate numeric values, just passes strings
        callback.answer.assert_awaited_once_with("Страница abc из xyz")
