"""Tests for catalog formatting utilities."""

from __future__ import annotations

import pytest

from app.utils import (
    format_price,
    format_product_button,
    resolve_badge,
    smart_truncate_name,
)


class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_price_simple(self):
        """Price 777 -> '777'."""
        assert format_price(777) == "777"

    def test_format_price_with_thousands(self):
        """Price 11700 -> '11 700'."""
        assert format_price(11700) == "11 700"

    def test_format_price_none(self):
        """None returns '0'."""
        assert format_price(None) == "0"


class TestSmartTruncateName:
    """Tests for smart_truncate_name function."""

    def test_short_name_unchanged(self):
        """Short names are not truncated."""
        assert smart_truncate_name("Махорка", 20) == "Махорка"

    def test_long_name_truncated(self):
        """Long names are truncated with ellipsis."""
        result = smart_truncate_name("Махорка СССР Премиум Коллекционная Редкая", 20)
        assert result.endswith("…")
        assert len(result) <= 20


class TestResolveBadge:
    """Tests for resolve_badge function."""

    def test_badge_hit(self):
        """#hit tag returns fire emoji."""
        product = {"tags": "#hit", "stock": 10}
        assert resolve_badge(product) == "🔥"

    def test_badge_new(self):
        """#new tag returns new emoji."""
        product = {"tags": "#new", "stock": 10}
        assert resolve_badge(product) == "🆕"

    def test_badge_sale(self):
        """#sale tag returns tag emoji."""
        product = {"tags": "#sale", "stock": 10}
        assert resolve_badge(product) == "🏷️"

    def test_badge_sale_priority(self):
        """#sale has priority over #hit and #new."""
        product = {"tags": "#sale, #hit, #new", "stock": 10}
        assert resolve_badge(product) == "🏷️"

    def test_badge_out_of_stock(self):
        """stock=0 returns stop emoji."""
        product = {"tags": "#hit", "stock": 0}
        assert resolve_badge(product) == "⛔️"

    def test_no_badge(self):
        """No special tags returns empty string."""
        product = {"tags": "regular", "stock": 10}
        assert resolve_badge(product) == ""


class TestFormatProductButton:
    """Tests for format_product_button function."""

    def test_short_name_with_price(self):
        """Short name formats correctly: 'Махорка — 1 000 ₽'."""
        product = {"name": "Махорка", "price_rub": 1000, "stock": 10, "tags": ""}
        result = format_product_button(product)
        assert result == "Махорка — 1 000 ₽"

    def test_long_name_truncation(self):
        """Long name is truncated and contains ellipsis."""
        product = {
            "name": "Махорка СССР Премиум Коллекционная Редкая Эксклюзивная",
            "price_rub": 500,
            "stock": 10,
            "tags": "",
        }
        result = format_product_button(product, max_total=48)
        assert "…" in result
        assert result.endswith(" — 500 ₽")
        assert len(result) <= 48

    def test_price_777(self):
        """Price 777 formats correctly."""
        product = {"name": "Товар", "price_rub": 777, "stock": 10, "tags": ""}
        result = format_product_button(product)
        assert result == "Товар — 777 ₽"

    def test_price_11700(self):
        """Price 11700 formats with space separator."""
        product = {"name": "Товар", "price_rub": 11700, "stock": 10, "tags": ""}
        result = format_product_button(product)
        assert result == "Товар — 11 700 ₽"

    def test_hit_badge(self):
        """#hit tag adds fire emoji prefix."""
        product = {"name": "Махорка СССР", "price_rub": 1000, "stock": 10, "tags": "#hit"}
        result = format_product_button(product)
        assert result == "🔥 Махорка СССР — 1 000 ₽"

    def test_new_badge(self):
        """#new tag adds new emoji prefix."""
        product = {"name": "Новинка Сезона", "price_rub": 850, "stock": 10, "tags": "#new"}
        result = format_product_button(product)
        assert result == "🆕 Новинка Сезона — 850 ₽"

    def test_sale_badge_priority(self):
        """#sale has priority over other badges."""
        product = {
            "name": "Акционный Товар",
            "price_rub": 900,
            "stock": 10,
            "tags": "#sale, #hit, #new",
        }
        result = format_product_button(product)
        assert result == "🏷️ Акционный Товар — 900 ₽"

    def test_out_of_stock(self):
        """stock=0 shows stop emoji and 'нет в наличии'."""
        product = {"name": "Редкий Товар", "price_rub": 1500, "stock": 0, "tags": "#hit"}
        result = format_product_button(product)
        assert result == "⛔️ Редкий Товар — нет в наличии"

    def test_with_package_weight(self):
        """Product with weight shows weight in name: 'Махорка СССР 50г — 500 ₽'."""
        product = {
            "name": "Махорка СССР",
            "price_rub": 500,
            "stock": 10,
            "tags": "#hit",
            "package_weight": 50,
        }
        result = format_product_button(product)
        assert result == "🔥 Махорка СССР 50г — 500 ₽"

    def test_without_package_weight(self):
        """Product without weight shows only name."""
        product = {
            "name": "Махорка Классическая",
            "price_rub": 777,
            "stock": 10,
            "tags": "",
            "package_weight": None,
        }
        result = format_product_button(product)
        assert result == "Махорка Классическая — 777 ₽"

    def test_weight_zero_not_shown(self):
        """Product with weight=0 (falsy) does not show weight."""
        product = {
            "name": "Товар",
            "price_rub": 500,
            "stock": 10,
            "tags": "",
            "package_weight": 0,
        }
        result = format_product_button(product)
        assert "г" not in result
        assert result == "Товар — 500 ₽"
