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
