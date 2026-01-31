"""Utility functions for Google Sheets operations."""


def col_letter(index: int) -> str:
    """Convert 0-based index to column letter (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    while index >= 0:
        result = chr(index % 26 + ord("A")) + result
        index = index // 26 - 1
    return result
