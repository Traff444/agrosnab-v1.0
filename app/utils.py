from __future__ import annotations

import html
import random
import re
import string
from datetime import UTC, datetime


def make_order_id(prefix: str = "ORD") -> str:
    ts = datetime.now(UTC).strftime("%y%m%d%H%M%S")
    rnd = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{ts}-{rnd}"


def escape_html(text: str) -> str:
    """
    Escape special characters for Telegram HTML parse mode.
    Handles: < > & and preserves other characters.
    """
    return html.escape(str(text))


# Phone validation regex: accepts international formats
_PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate phone number.
    Returns (is_valid, cleaned_phone_or_error).
    """
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if not cleaned:
        return False, "Номер телефона не указан"
    if not _PHONE_RE.match(cleaned):
        return False, "Некорректный формат телефона. Пример: +79991234567"
    return True, cleaned


# ---------------------------------------------------------------------------
# Catalog formatting utilities
# ---------------------------------------------------------------------------

BADGE_BY_TAG = {"#sale": "🏷️", "#hit": "🔥", "#new": "🆕"}
BADGE_PRIORITY = ["#sale", "#hit", "#new"]


def format_price(price: int | None) -> str:
    """Format price with spaces as thousand separators.

    11700 -> '11 700'
    """
    if price is None:
        return "0"
    return f"{int(price):,}".replace(",", " ")


def _parse_tags(tags: str | None) -> set[str]:
    """Parse comma or semicolon separated tags into a set."""
    if not tags:
        return set()
    raw = tags.replace(";", ",").split(",")
    return {t.strip().lower() for t in raw if t.strip()}


def resolve_badge(product) -> str:
    """Resolve badge emoji based on product status.

    Priority: stock=0 -> sale -> hit -> new
    """
    # Support both object and dict
    if isinstance(product, dict):
        tags_str = product.get("tags")
        stock = product.get("stock", 1)
    else:
        tags_str = getattr(product, "tags", None)
        stock = getattr(product, "stock", 1)

    if stock == 0:
        return "⛔️"

    tags_set = _parse_tags(tags_str)
    for tag in BADGE_PRIORITY:
        if tag in tags_set:
            return BADGE_BY_TAG[tag]
    return ""


def smart_truncate_name(name: str, max_len: int) -> str:
    """Truncate name by words, adding ellipsis if needed."""
    name = " ".join((name or "").split())
    if max_len <= 0:
        return "…"
    if len(name) <= max_len:
        return name
    words = name.split()
    out: list[str] = []
    for w in words:
        candidate = " ".join(out + [w]) + "…"
        if len(candidate) <= max_len:
            out.append(w)
        else:
            break
    if out:
        return " ".join(out) + "…"
    return name[: max_len - 1] + "…"


def format_product_button(product, max_total: int = 48) -> str:
    """Build product button text: 'badge Name — price ₽' or 'badge Name — нет в наличии'.

    Examples:
        - "Махорка — 1 000 ₽"
        - "🔥 Махорка СССР — 1 000 ₽"
        - "⛔️ Редкий Товар — нет в наличии"
    """
    badge = resolve_badge(product)
    prefix = f"{badge} " if badge else ""

    # Support both object and dict
    if isinstance(product, dict):
        stock = product.get("stock", 1)
        name_raw = product.get("name", "")
        price_value = product.get("price_rub") or product.get("price", 0)
    else:
        stock = getattr(product, "stock", 1)
        name_raw = getattr(product, "name", "")
        price_value = getattr(product, "price_rub", None) or getattr(product, "price", 0)

    if stock == 0:
        suffix = " — нет в наличии"
        max_name_len = max_total - len(suffix) - len(prefix)
        name = smart_truncate_name(name_raw, max_name_len)
        return f"{prefix}{name}{suffix}"

    price_str = f" — {format_price(price_value)} ₽"
    max_name_len = max_total - len(price_str) - len(prefix)
    name = smart_truncate_name(name_raw, max_name_len)
    return f"{prefix}{name}{price_str}"
