"""Data models for sheets operations."""

from dataclasses import dataclass


@dataclass
class StockOperationResult:
    """Result of a stock operation (writeoff, correction, archive)."""

    ok: bool
    stock_before: int
    stock_after: int
    operation_id: str
    error: str | None = None
