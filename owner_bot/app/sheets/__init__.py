"""Google Sheets client package.

This package provides a modular client for Google Sheets operations:
- client.py: Base client with connection and column mapping
- products.py: Product CRUD operations
- logging.py: Stock logging (Внесение/Списание)
- crm.py: CRM operations (Leads, Orders)
- utils.py: Utility functions
- constants.py: Column definitions and constants
- models.py: Data models
"""

from .client import BaseSheetsClient
from .constants import (
    COL_ALIASES,
    DEDUP_LOOKBACK_ROWS,
    LEADS_COLUMNS,
    LOG_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    SCOPES,
)
from .crm import CRMOperationsMixin
from .logging import LoggingOperationsMixin
from .models import StockOperationResult
from .products import ProductOperationsMixin


class SheetsClient(
    BaseSheetsClient,
    ProductOperationsMixin,
    LoggingOperationsMixin,
    CRMOperationsMixin,
):
    """Full-featured Google Sheets client combining all operations."""

    pass


# Global client instance for backward compatibility
sheets_client = SheetsClient()

__all__ = [
    "SheetsClient",
    "sheets_client",
    "StockOperationResult",
    "BaseSheetsClient",
    "ProductOperationsMixin",
    "LoggingOperationsMixin",
    "CRMOperationsMixin",
    "SCOPES",
    "REQUIRED_COLUMNS",
    "OPTIONAL_COLUMNS",
    "COL_ALIASES",
    "LOG_COLUMNS",
    "LEADS_COLUMNS",
    "DEDUP_LOOKBACK_ROWS",
]
