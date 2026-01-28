"""Tests for intake string parser."""

import pytest

from app.intake_parser import parse_intake_string, format_parsed_intake
from app.models import IntakeConfidence


class TestParseIntakeString:
    """Test cases for parse_intake_string function."""

    def test_full_quick_string(self):
        """Test parsing complete quick string with name, price, quantity."""
        result = parse_intake_string("Махорка СССР 500 10")

        assert "Махорка СССР" in result.name
        assert result.price == 500.0
        assert result.quantity == 10
        assert result.confidence == IntakeConfidence.HIGH

    def test_quick_string_with_price_suffix(self):
        """Test parsing with price suffix (р, руб, ₽)."""
        test_cases = [
            ("Товар 100р 5", 100.0, 5),
            ("Товар 100 руб 5", 100.0, 5),
            ("Товар 100₽ 5", 100.0, 5),
        ]

        for input_str, expected_price, expected_qty in test_cases:
            result = parse_intake_string(input_str)
            assert result.price == expected_price, f"Failed for: {input_str}"
            assert result.quantity == expected_qty, f"Failed for: {input_str}"

    def test_quick_string_with_quantity_suffix(self):
        """Test parsing with quantity suffix (шт, ед)."""
        test_cases = [
            ("Товар 200 10шт", 200.0, 10),
            ("Товар 200 10 шт.", 200.0, 10),
        ]

        for input_str, expected_price, expected_qty in test_cases:
            result = parse_intake_string(input_str)
            assert result.price == expected_price, f"Failed for: {input_str}"
            assert result.quantity == expected_qty, f"Failed for: {input_str}"

    def test_name_only_low_confidence(self):
        """Test parsing name-only input results in low confidence."""
        result = parse_intake_string("Махорка")

        assert result.name == "Махорка"
        assert result.price is None
        assert result.quantity is None
        assert result.confidence == IntakeConfidence.LOW

    def test_name_with_one_number(self):
        """Test parsing name with single number (ambiguous)."""
        result = parse_intake_string("Товар 500")

        assert "Товар" in result.name
        # Single large number assumed to be price
        assert result.price == 500.0
        assert result.quantity is None
        assert result.confidence == IntakeConfidence.LOW

    def test_name_with_small_number(self):
        """Test small number is interpreted as quantity."""
        result = parse_intake_string("Товар 5")

        assert "Товар" in result.name
        # Single small number assumed to be quantity
        assert result.quantity == 5
        assert result.confidence == IntakeConfidence.LOW

    def test_decimal_price(self):
        """Test parsing decimal prices."""
        result = parse_intake_string("Товар 99.50 3")

        assert result.price == 99.50
        assert result.quantity == 3

    def test_comma_decimal(self):
        """Test parsing prices with comma decimal separator."""
        result = parse_intake_string("Товар 99,50 3")

        assert result.price == 99.50
        assert result.quantity == 3

    def test_empty_string(self):
        """Test parsing empty string."""
        result = parse_intake_string("")

        assert result.name is None
        assert result.price is None
        assert result.quantity is None
        assert result.confidence == IntakeConfidence.LOW

    def test_whitespace_only(self):
        """Test parsing whitespace-only string."""
        result = parse_intake_string("   ")

        assert result.confidence == IntakeConfidence.LOW

    def test_raw_input_preserved(self):
        """Test that raw_input is always preserved."""
        input_str = "Test 100 5"
        result = parse_intake_string(input_str)

        assert result.raw_input == input_str

    def test_multiword_name(self):
        """Test parsing multiword product names."""
        result = parse_intake_string("Чай черный байховый 250 20")

        assert "Чай" in result.name
        assert result.price == 250.0
        assert result.quantity == 20

    def test_cyrillic_handling(self):
        """Test proper handling of Cyrillic text."""
        result = parse_intake_string("Кофе растворимый 300 15")

        assert "Кофе" in result.name
        assert result.price == 300.0
        assert result.quantity == 15


class TestFormatParsedIntake:
    """Test cases for format_parsed_intake function."""

    def test_format_full_intake(self):
        """Test formatting complete intake."""
        from app.models import ParsedIntake

        parsed = ParsedIntake(
            name="Test Product",
            price=500.0,
            quantity=10,
            confidence=IntakeConfidence.HIGH,
            raw_input="Test Product 500 10",
        )

        formatted = format_parsed_intake(parsed)

        assert "Test Product" in formatted
        assert "500" in formatted
        assert "10" in formatted
        assert "высокая" in formatted

    def test_format_partial_intake(self):
        """Test formatting partial intake."""
        from app.models import ParsedIntake

        parsed = ParsedIntake(
            name="Test",
            price=None,
            quantity=None,
            confidence=IntakeConfidence.LOW,
            raw_input="Test",
        )

        formatted = format_parsed_intake(parsed)

        assert "Test" in formatted
        assert "требует уточнения" in formatted
