"""Tests for utility functions."""

import re


class TestMakeOrderId:
    """Tests for make_order_id() function."""

    def test_default_prefix(self):
        from app.utils import make_order_id

        order_id = make_order_id()
        assert order_id.startswith("ORD-")

    def test_custom_prefix(self):
        from app.utils import make_order_id

        order_id = make_order_id(prefix="TEST")
        assert order_id.startswith("TEST-")

    def test_format_structure(self):
        from app.utils import make_order_id

        order_id = make_order_id()
        # Format: PREFIX-YYMMDDHHMMSS-XXXX
        parts = order_id.split("-")
        assert len(parts) == 3
        assert parts[0] == "ORD"
        assert len(parts[1]) == 12  # YYMMDDHHMMSS
        assert len(parts[2]) == 4  # Random suffix

    def test_timestamp_is_numeric(self):
        from app.utils import make_order_id

        order_id = make_order_id()
        parts = order_id.split("-")
        timestamp = parts[1]
        assert timestamp.isdigit()

    def test_random_suffix_is_alphanumeric(self):
        from app.utils import make_order_id

        order_id = make_order_id()
        parts = order_id.split("-")
        suffix = parts[2]
        assert suffix.isalnum()
        assert suffix.isupper() or suffix.isdigit()

    def test_uniqueness(self):
        from app.utils import make_order_id

        # Generate multiple IDs and check they're unique
        ids = {make_order_id() for _ in range(100)}
        assert len(ids) == 100

    def test_empty_prefix(self):
        from app.utils import make_order_id

        order_id = make_order_id(prefix="")
        assert order_id.startswith("-")

    def test_long_prefix(self):
        from app.utils import make_order_id

        order_id = make_order_id(prefix="VERY_LONG_PREFIX")
        assert order_id.startswith("VERY_LONG_PREFIX-")


class TestEscapeHtml:
    """Tests for escape_html() function."""

    def test_escape_less_than(self):
        from app.utils import escape_html

        assert escape_html("<") == "&lt;"
        assert escape_html("a < b") == "a &lt; b"

    def test_escape_greater_than(self):
        from app.utils import escape_html

        assert escape_html(">") == "&gt;"
        assert escape_html("a > b") == "a &gt; b"

    def test_escape_ampersand(self):
        from app.utils import escape_html

        assert escape_html("&") == "&amp;"
        assert escape_html("Tom & Jerry") == "Tom &amp; Jerry"

    def test_escape_quotes(self):
        from app.utils import escape_html

        # html.escape escapes quotes by default
        assert "&quot;" in escape_html('"quote"') or '"' in escape_html('"quote"')

    def test_no_escape_needed(self):
        from app.utils import escape_html

        text = "Hello World 123"
        assert escape_html(text) == text

    def test_mixed_content(self):
        from app.utils import escape_html

        result = escape_html("<script>alert('XSS')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_cyrillic_preserved(self):
        from app.utils import escape_html

        text = "Привет мир"
        assert escape_html(text) == text

    def test_empty_string(self):
        from app.utils import escape_html

        assert escape_html("") == ""

    def test_non_string_input(self):
        from app.utils import escape_html

        # Function converts to string
        assert escape_html(123) == "123"
        assert escape_html(None) == "None"

    def test_multiple_special_chars(self):
        from app.utils import escape_html

        result = escape_html("<tag> & </tag>")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result


class TestValidatePhone:
    """Tests for validate_phone() function."""

    def test_valid_russian_phone(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("+79991234567")
        assert is_valid is True
        assert result == "+79991234567"

    def test_valid_phone_without_plus(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("79991234567")
        assert is_valid is True
        assert result == "79991234567"

    def test_valid_phone_with_spaces(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("+7 999 123 45 67")
        assert is_valid is True
        assert result == "+79991234567"

    def test_valid_phone_with_dashes(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("+7-999-123-45-67")
        assert is_valid is True
        assert result == "+79991234567"

    def test_valid_phone_with_parentheses(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("+7(999)1234567")
        assert is_valid is True
        assert result == "+79991234567"

    def test_valid_phone_mixed_formatting(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("+7 (999) 123-45-67")
        assert is_valid is True
        assert result == "+79991234567"

    def test_valid_international_phone(self):
        from app.utils import validate_phone

        # US phone
        is_valid, result = validate_phone("+14155551234")
        assert is_valid is True

        # UK phone
        is_valid, result = validate_phone("+442071234567")
        assert is_valid is True

    def test_invalid_empty_phone(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("")
        assert is_valid is False
        assert "не указан" in error

    def test_invalid_whitespace_only(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("   ")
        assert is_valid is False
        assert "не указан" in error

    def test_invalid_too_short(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("+7999123")
        assert is_valid is False
        assert "Некорректный" in error

    def test_invalid_too_long(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("+79991234567890123")
        assert is_valid is False
        assert "Некорректный" in error

    def test_invalid_letters(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("+7999abc4567")
        assert is_valid is False
        assert "Некорректный" in error

    def test_invalid_special_chars(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("+7999!234567")
        assert is_valid is False
        assert "Некорректный" in error

    def test_strips_leading_trailing_whitespace(self):
        from app.utils import validate_phone

        is_valid, result = validate_phone("  +79991234567  ")
        assert is_valid is True
        assert result == "+79991234567"

    def test_minimum_length_phone(self):
        from app.utils import validate_phone

        # 10 digits is minimum
        is_valid, result = validate_phone("1234567890")
        assert is_valid is True

    def test_maximum_length_phone(self):
        from app.utils import validate_phone

        # 15 digits is maximum
        is_valid, result = validate_phone("123456789012345")
        assert is_valid is True

    def test_error_message_contains_example(self):
        from app.utils import validate_phone

        is_valid, error = validate_phone("invalid")
        assert is_valid is False
        assert "+79991234567" in error or "Пример" in error


class TestPhoneRegex:
    """Tests for phone validation regex pattern."""

    def test_regex_pattern_exists(self):
        from app.utils import _PHONE_RE

        assert _PHONE_RE is not None
        assert isinstance(_PHONE_RE, re.Pattern)

    def test_regex_accepts_plus_prefix(self):
        from app.utils import _PHONE_RE

        assert _PHONE_RE.match("+79991234567")

    def test_regex_accepts_no_plus(self):
        from app.utils import _PHONE_RE

        assert _PHONE_RE.match("79991234567")

    def test_regex_rejects_letters(self):
        from app.utils import _PHONE_RE

        assert _PHONE_RE.match("7999abc4567") is None
