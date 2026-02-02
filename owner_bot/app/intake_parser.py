"""Parser for quick intake strings."""

import re
from typing import NamedTuple

from app.models import IntakeConfidence, ParsedIntake


class TokenPattern(NamedTuple):
    """Pattern for token extraction."""

    pattern: str
    name: str


# Common patterns for prices (with optional currency markers)
PRICE_PATTERNS = [
    r"(\d+(?:[.,]\d{1,2})?)\s*(?:р(?:уб)?\.?|₽)?",  # 500р, 500 руб, 500₽
    r"(?:₽|р(?:уб)?\.?)\s*(\d+(?:[.,]\d{1,2})?)",  # ₽500, руб 500
]

# Quantity patterns
QUANTITY_PATTERNS = [
    r"(\d+)\s*(?:шт\.?|ед\.?|x|х)?$",  # 10шт, 10 ед, x10
    r"(?:x|х)\s*(\d+)",  # x10, х5
]

# Weight pattern (package weight in grams)
WEIGHT_PATTERN = re.compile(r"(\d+)\s*[гg](?:\s|$|[^a-zA-Zа-яА-Я])", re.IGNORECASE)


def _extract_weight(text: str) -> tuple[int | None, str]:
    """Extract package weight from text. Returns (weight_grams, text_without_weight)."""
    match = WEIGHT_PATTERN.search(text)
    if match:
        weight = int(match.group(1))
        # Validate reasonable weight range (1g to 100kg)
        if 1 <= weight <= 100000:
            # Remove the weight token from text
            text_without_weight = text[: match.start()] + text[match.end() :]
            text_without_weight = re.sub(r"\s+", " ", text_without_weight).strip()
            return weight, text_without_weight
    return None, text


def _extract_numbers(text: str) -> list[tuple[float, int, int]]:
    """Extract all numbers with their positions. Returns (value, start, end)."""
    numbers = []
    for match in re.finditer(r"\d+(?:[.,]\d+)?", text):
        value = float(match.group().replace(",", "."))
        numbers.append((value, match.start(), match.end()))
    return numbers


def _clean_text(text: str) -> str:
    """Remove extracted numbers and cleanup text."""
    # Remove numbers with common suffixes (number must be preceded by space)
    text = re.sub(r"\s\d+(?:[.,]\d+)?\s*(?:р(?:уб)?\.?|₽|шт\.?|ед\.?)(?:\s|$)", " ", text)
    # Remove currency prefix + number (prefix must be preceded by space or at start)
    text = re.sub(r"(?:^|\s)(?:₽|руб\.?)\s*\d+(?:[.,]\d+)?", " ", text)
    # Remove standalone numbers only when surrounded by whitespace
    text = re.sub(r"(?<=\s)\d+(?:[.,]\d+)?(?=\s|$)", "", text)
    text = re.sub(r"^\d+(?:[.,]\d+)?(?=\s|$)", "", text)
    # Cleanup whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_intake_string(raw_input: str) -> ParsedIntake:
    """
    Parse quick intake string.

    Expected formats:
    - "Махорка СССР 50г 500 10" → name="Махорка СССР", weight=50, price=500, qty=10
    - "Махорка СССР 500 10" → name="Махорка СССР", price=500, qty=10
    - "Тест" → name="Тест", confidence=low
    - "Новый товар 1500р 5шт" → name="Новый товар", price=1500, qty=5

    Heuristics:
    - Weight is extracted first by suffix "г" or "g" (e.g., 50г, 100g)
    - Last number is usually quantity (if reasonable: 1-1000)
    - Previous number is usually price (if reasonable: 1-1000000)
    - Everything else is name
    """
    raw_input = raw_input.strip()

    if not raw_input:
        return ParsedIntake(raw_input=raw_input, confidence=IntakeConfidence.LOW)

    # Extract weight first (by suffix "г" or "g")
    weight, text_after_weight = _extract_weight(raw_input)

    numbers = _extract_numbers(text_after_weight)

    # No numbers - just a name with low confidence
    if not numbers:
        return ParsedIntake(
            name=text_after_weight if text_after_weight else raw_input,
            weight=weight,
            raw_input=raw_input,
            confidence=IntakeConfidence.LOW,
        )

    # Extract potential values
    name = None
    price = None
    quantity = None

    if len(numbers) >= 2:
        # Two or more numbers: assume "name price quantity"
        # Last reasonable number is quantity, previous is price
        candidates = sorted(numbers, key=lambda x: x[1])  # Sort by position

        # Find quantity (last number, should be reasonable: 1-1000)
        for val, start, _end in reversed(candidates):
            if 1 <= val <= 1000 and val == int(val):
                quantity = int(val)
                candidates = [c for c in candidates if c[1] != start]
                break

        # Find price (remaining numbers, prefer larger reasonable value)
        for val, _start, _end in reversed(candidates):
            if 1 <= val <= 1000000:
                price = val
                break

        # Extract name (text before first number or cleaned text)
        name = _clean_text(text_after_weight)

        if name and price and quantity:
            return ParsedIntake(
                name=name,
                price=price,
                quantity=quantity,
                weight=weight,
                raw_input=raw_input,
                confidence=IntakeConfidence.HIGH,
            )

    elif len(numbers) == 1:
        # One number - could be price or quantity
        val, start, end = numbers[0]
        name = _clean_text(text_after_weight)

        # If small integer, likely quantity
        if 1 <= val <= 100 and val == int(val):
            quantity = int(val)
        else:
            # Otherwise assume price
            price = val

        return ParsedIntake(
            name=name if name else None,
            price=price,
            quantity=quantity,
            weight=weight,
            raw_input=raw_input,
            confidence=IntakeConfidence.LOW,
        )

    # Fallback: return what we have with low confidence
    name = _clean_text(text_after_weight) or text_after_weight

    return ParsedIntake(
        name=name,
        price=price,
        quantity=quantity,
        weight=weight,
        raw_input=raw_input,
        confidence=IntakeConfidence.LOW if not (price and quantity) else IntakeConfidence.HIGH,
    )


def format_parsed_intake(parsed: ParsedIntake) -> str:
    """Format parsed intake for preview."""
    lines = []

    if parsed.name:
        lines.append(f"📦 **Товар:** {parsed.name}")
    if parsed.weight is not None:
        lines.append(f"⚖️ **Вес:** {parsed.weight} г")
    if parsed.price is not None:
        lines.append(f"💰 **Цена:** {parsed.price:.2f} ₽")
    if parsed.quantity is not None:
        lines.append(f"📊 **Количество:** {parsed.quantity} шт.")

    confidence_emoji = "✅" if parsed.confidence == IntakeConfidence.HIGH else "⚠️"
    confidence_text = (
        "высокая" if parsed.confidence == IntakeConfidence.HIGH else "требует уточнения"
    )
    lines.append(f"{confidence_emoji} **Уверенность:** {confidence_text}")

    return "\n".join(lines)
