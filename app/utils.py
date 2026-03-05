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
def validate_fio(fio: str) -> tuple[bool, str]:
    """
    Validate full name (ФИО).
    Returns (is_valid, cleaned_fio_or_error).
    """
    cleaned = " ".join(fio.strip().split())
    if len(cleaned) < 3:
        return False, "ФИО слишком короткое (мин. 3 символа)"
    if len(cleaned) > 100:
        return False, "ФИО слишком длинное (макс. 100 символов)"
    return True, cleaned


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate Russian phone number.
    Accepts: +79991234567, 89991234567, 79991234567
    Returns (is_valid, normalized_phone_or_error).
    """
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if not cleaned:
        return False, "Номер телефона не указан"

    # Normalize: 8xxx -> +7xxx, 7xxx -> +7xxx
    if cleaned.startswith("8") and len(cleaned) == 11:
        cleaned = "+7" + cleaned[1:]
    elif cleaned.startswith("7") and len(cleaned) == 11:
        cleaned = "+7" + cleaned[1:]
    elif cleaned.startswith("+7") and len(cleaned) == 12:
        pass  # already correct
    else:
        return False, "Введите номер в формате +79991234567 или 89991234567"

    # Validate: +7 followed by 10 digits
    if not re.match(r"^\+7[0-9]{10}$", cleaned):
        return False, "Введите номер в формате +79991234567 или 89991234567"

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


def format_catalog_text_line(
    index: int,
    product,
    name_width: int = 22,
    price_width: int = 8,
) -> str:
    """Format one catalog line for <pre> block: '1. Махорка СССР 70г    90 ₽'"""
    if isinstance(product, dict):
        name_raw = product.get("name", "")
        price_value = product.get("price_rub") or product.get("price", 0)
        stock = product.get("stock", 1)
        weight = product.get("package_weight")
    else:
        name_raw = getattr(product, "name", "")
        price_value = getattr(product, "price_rub", None) or getattr(product, "price", 0)
        stock = getattr(product, "stock", 1)
        weight = getattr(product, "package_weight", None)

    if weight:
        name_raw = f"{name_raw} {weight}г"

    num_prefix = f"{index}. "
    available_name = name_width - len(num_prefix)
    name = smart_truncate_name(name_raw, max(available_name, 8))

    if stock == 0:
        price_part = "--- ₽"
    else:
        price_part = f"{format_price(price_value)} ₽"

    price_padded = price_part.rjust(price_width)
    name_padded = f"{num_prefix}{name}".ljust(name_width)
    return f"{name_padded}{price_padded}"


def format_catalog_page_text(
    products_page: list,
    page: int,
    total_pages: int,
    total_items: int,
    category_label: str = "",
) -> str:
    """Build minimal catalog header text."""
    header = "🌿 <b>MahorkaMarket</b>"
    if category_label and category_label != "Все товары":
        header += f" • {category_label}"

    if not products_page:
        return f"{header}\n\nКаталог пуст."

    return f"{header}\n\nВыберите товар:"


def _clean_product_name(name: str) -> str:
    """Clean product name: strip Махорка, quotes, крупка, NEW."""
    import re
    name = re.sub(r'^[Мм]ахорка\s*', '', name)
    name = name.replace('"', '').replace('\u00ab', '').replace('\u00bb', '')
    name = re.sub(r'\b[Кк]рупка\b', '', name)
    name = re.sub(r'\bNEW\b', '', name)
    return ' '.join(name.split()).strip()


def format_product_button(product, max_total: int = 48) -> str:
    """Build clean product button: '🌿 СССР • 70г — 90 ₽'."""
    badge = resolve_badge(product)

    if isinstance(product, dict):
        stock = product.get("stock", 1)
        name_raw = product.get("name", "")
        price_value = product.get("price_rub") or product.get("price", 0)
        weight = product.get("package_weight")
    else:
        stock = getattr(product, "stock", 1)
        name_raw = getattr(product, "name", "")
        price_value = getattr(product, "price_rub", None) or getattr(product, "price", 0)
        weight = getattr(product, "package_weight", None)

    name_raw = _clean_product_name(name_raw)
    prefix = f"{badge} " if badge else "🌿 "

    if stock == 0:
        if weight:
            suffix = f" • {weight}г — нет"
        else:
            suffix = " • нет"
        max_name_len = max_total - len(suffix) - len(prefix)
        name = smart_truncate_name(name_raw, max_name_len)
        return f"{prefix}{name}{suffix}"

    if weight:
        price_str = f" • {weight}г — {format_price(price_value)} ₽"
    else:
        price_str = f" — {format_price(price_value)} ₽"
    max_name_len = max_total - len(price_str) - len(prefix)
    name = smart_truncate_name(name_raw, max_name_len)
    return f"{prefix}{name}{price_str}"
