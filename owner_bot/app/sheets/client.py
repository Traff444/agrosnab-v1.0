"""Base Google Sheets client with connection and column mapping."""

import logging
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from ..config import get_settings
from .constants import COL_ALIASES, REQUIRED_COLUMNS, SCOPES
from .utils import col_letter

logger = logging.getLogger(__name__)


class BaseSheetsClient:
    """Base Google Sheets client with dynamic column mapping."""

    def __init__(self):
        self._service = None
        self._col_map: dict[str, int] = {}
        self._headers: list[str] = []
        self._sheet_name = "Склад"
        self._log_col_map_cache: dict[str, dict[str, int]] = {}

    def _get_credentials(self) -> Credentials:
        """Get Google credentials from settings."""
        settings = get_settings()
        info = settings.get_google_credentials_info()
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    @property
    def service(self):
        """Lazy-loaded Sheets service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("sheets", "v4", credentials=creds)
        return self._service

    def _col_letter(self, index: int) -> str:
        """Convert 0-based index to column letter."""
        return col_letter(index)

    def _col_idx(self, name: str) -> int:
        """Get column index by name, supporting aliases."""
        if name in self._col_map:
            return self._col_map[name]
        alias = COL_ALIASES.get(name)
        if alias and alias in self._col_map:
            return self._col_map[alias]
        raise KeyError(f"Column not found: {name}")

    async def load_column_map(self) -> dict[str, int]:
        """Load column mapping from sheet headers."""
        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!1:1",
            )
            .execute()
        )

        headers = result.get("values", [[]])[0]
        self._headers = headers
        self._col_map = {header: idx for idx, header in enumerate(headers)}

        missing = [col for col in REQUIRED_COLUMNS if col not in self._col_map]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        return self._col_map

    @property
    def col_map(self) -> dict[str, int]:
        """Get column mapping (must call load_column_map first)."""
        if not self._col_map:
            raise RuntimeError("Column map not loaded. Call load_column_map() first.")
        return self._col_map

    def _row_to_dict(self, row: list[Any]) -> dict[str, Any]:
        """Convert row list to dict using column map."""
        result = {}
        for col_name, col_idx in self._col_map.items():
            if col_idx < len(row):
                result[col_name] = row[col_idx]
            else:
                result[col_name] = ""
        return result

    async def test_connection(self) -> dict[str, Any]:
        """Test connection and return diagnostic info."""
        settings = get_settings()

        try:
            result = (
                self.service.spreadsheets()
                .get(spreadsheetId=settings.google_sheets_id)
                .execute()
            )

            sheets = [s["properties"]["title"] for s in result.get("sheets", [])]
            has_stock_sheet = self._sheet_name in sheets

            col_map = await self.load_column_map() if has_stock_sheet else {}
            missing_cols = [c for c in REQUIRED_COLUMNS if c not in col_map]

            return {
                "ok": has_stock_sheet and not missing_cols,
                "spreadsheet_title": result.get("properties", {}).get("title", ""),
                "sheets": sheets,
                "has_stock_sheet": has_stock_sheet,
                "columns_found": list(col_map.keys()),
                "missing_columns": missing_cols,
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }
