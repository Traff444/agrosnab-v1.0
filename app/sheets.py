from __future__ import annotations

import asyncio
import logging
import pathlib
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# CRM Stage priorities (higher = further in funnel)
STAGE_PRIORITY = {
    'new': 1,
    'engaged': 2,
    'cart': 3,
    'checkout': 4,
    'customer': 5,
    'repeat': 6,
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

T = TypeVar("T")


async def retry_async(
    fn: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """
    Retry an async function with exponential backoff.
    Useful for transient Google Sheets API errors (429, 500, 503).
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await fn(*args, **kwargs)
        except HttpError as e:
            # Retry on rate limit or server errors
            if e.resp.status in (429, 500, 503):
                last_exc = e
                wait = delay * (2**attempt)
                logger.warning(
                    "Sheets API error %s, retrying in %.1fs (attempt %d/%d)",
                    e.resp.status,
                    wait,
                    attempt + 1,
                    retries,
                )
                await asyncio.sleep(wait)
            else:
                raise
        except Exception as e:
            last_exc = e
            wait = delay * (2**attempt)
            logger.warning(
                "Sheets error: %s, retrying in %.1fs (attempt %d/%d)",
                e,
                wait,
                attempt + 1,
                retries,
            )
            await asyncio.sleep(wait)
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_async exhausted without result")


def convert_photo_url(url: str) -> str:
    """
    Convert various image hosting URLs to direct links.
    Supports: Google Drive, Dropbox
    """
    if not url:
        return ""

    url = url.strip()

    # Google Drive: /file/d/{ID}/view → /uc?export=view&id={ID}
    gdrive_match = re.search(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", url)
    if gdrive_match:
        file_id = gdrive_match.group(1)
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    # Google Drive already in correct format
    if "drive.google.com/uc" in url:
        return url

    # Dropbox: change dl=0 to dl=1
    if "dropbox.com" in url:
        return url.replace("dl=0", "dl=1")

    return url


class SheetsClient:
    """Google Sheets client with sync methods and async wrappers."""

    def __init__(self, spreadsheet_id: str, service_account_json_path: str):
        self.spreadsheet_id = spreadsheet_id
        cred_path = pathlib.Path(service_account_json_path)
        creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
        self.service = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # -------------------------------------------------------------------------
    # Low-level sync methods (blocking)
    # -------------------------------------------------------------------------
    def _get_values_sync(self, a1: str) -> list[list[Any]]:
        resp = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=a1)
            .execute()
        )
        return resp.get("values", [])

    def _append_values_sync(self, a1: str, rows: list[list[Any]]) -> None:
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=a1,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    def _update_values_sync(self, a1: str, values: list[list[Any]]) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=a1,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    def _batch_update_values_sync(self, data: list[dict[str, Any]]) -> None:
        """Batch update multiple ranges in a single API call."""
        if not data:
            return
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()

    # -------------------------------------------------------------------------
    # Async wrappers (run blocking IO in thread pool)
    # -------------------------------------------------------------------------
    async def get_values(self, a1: str) -> list[list[Any]]:
        return await asyncio.to_thread(self._get_values_sync, a1)

    async def append_values(self, a1: str, rows: list[list[Any]]) -> None:
        await asyncio.to_thread(self._append_values_sync, a1, rows)

    async def update_values(self, a1: str, values: list[list[Any]]) -> None:
        await asyncio.to_thread(self._update_values_sync, a1, values)

    async def batch_update_values(self, data: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._batch_update_values_sync, data)

    # Backwards-compatible sync aliases for non-async callers (services/caches)
    def get_values_sync(self, a1: str) -> list[list[Any]]:
        return self._get_values_sync(a1)

    def append_values_sync(self, a1: str, rows: list[list[Any]]) -> None:
        self._append_values_sync(a1, rows)

    def update_values_sync(self, a1: str, values: list[list[Any]]) -> None:
        self._update_values_sync(a1, values)

    # -------------------------------------------------------------------------
    # Business methods
    # -------------------------------------------------------------------------
    async def decrease_stock(self, sku_qty_list: list[tuple]) -> None:
        """
        Decrease stock for given SKUs in Склад sheet using batch update.
        sku_qty_list: [(sku, qty_to_subtract), ...]
        """
        if not sku_qty_list:
            return

        rows = await self.get_values("Склад!A1:M1000")
        if not rows:
            return

        header = [str(h).strip().lower() for h in rows[0]]

        sku_col = None
        spisano_col = None
        for i, h in enumerate(header):
            if "sku" in h or "артикул" in h:
                sku_col = i
            if "списано" in h:
                spisano_col = i

        if sku_col is None or spisano_col is None:
            logger.warning("decrease_stock: required columns not found")
            return

        sku_to_subtract = {s: q for s, q in sku_qty_list}
        batch_data: list[dict[str, Any]] = []

        for row_idx, row in enumerate(rows[1:], start=2):
            if len(row) <= sku_col:
                continue
            sku = str(row[sku_col]).strip()
            if sku not in sku_to_subtract:
                continue

            current = 0
            if len(row) > spisano_col and row[spisano_col]:
                try:
                    current = int(float(str(row[spisano_col]).replace(" ", "").replace(",", ".")))
                except Exception:
                    current = 0
            new_value = current + sku_to_subtract[sku]
            cell = f"Склад!{chr(65 + spisano_col)}{row_idx}"
            batch_data.append({"range": cell, "values": [[new_value]]})

        if batch_data:
            await self.batch_update_values(batch_data)

    def get_settings(self) -> dict[str, Any]:
        rows = self.get_values_sync("Настройки!A2:B200")
        out: dict[str, Any] = {}
        for r in rows:
            if len(r) < 2:
                continue
            k = str(r[0]).strip()
            v = r[1]
            if not k:
                continue
            out[k] = v
        return out

    def get_products(self) -> list[dict[str, Any]]:
        """
        Flexible product parser that works with different table structures.
        Required columns: SKU, Наименование, Цена (or Цена_руб)
        Optional: Описание_кратко, Остаток (or Стартовый_остаток or Остаток_расчет), Активен, Теги, Фото_URL
        """
        try:
            rows = self.get_values_sync("Склад!A1:M1000")
        except Exception:
            return []

        if not rows:
            return []

        header = [str(h).strip().lower() for h in rows[0]]
        data = rows[1:]

        # Build column index map (flexible matching)
        def find_col(names: list) -> int:
            for name in names:
                for i, h in enumerate(header):
                    if name.lower() in h:
                        return i
            return -1

        col_sku = find_col(["sku", "артикул", "код"])
        col_name = find_col(["наименование", "название", "товар"])
        col_price = find_col(["цена", "price", "стоимость"])
        col_desc = find_col(["описание_кратко", "описание", "desc"])
        col_desc_full = find_col(["описание_полное", "полное"])
        col_stock = find_col(["остаток_расчет", "остаток", "stock", "стартовый"])
        col_active = find_col(["активен", "active", "вкл"])
        col_tags = find_col(["теги", "tags", "категория"])
        col_photo = find_col(["фото", "photo", "url", "картинка", "изображение"])

        if col_sku == -1 or col_name == -1:
            return []  # Minimal required columns

        def to_int(x, default=0):
            try:
                # Handle non-breaking spaces (\xa0) and regular spaces
                clean = (
                    str(x).replace("\xa0", "").replace(" ", "").replace("₽", "").replace(",", ".")
                )
                return int(float(clean))
            except Exception:
                return default

        def safe_get(row, idx, default=""):
            if idx == -1 or idx >= len(row):
                return default
            return str(row[idx]).strip()

        products = []
        for r in data:
            sku = safe_get(r, col_sku)
            if not sku:
                continue

            # Check "Активен" column if exists, otherwise assume active
            if col_active != -1:
                active_val = safe_get(r, col_active).lower()
                if active_val and active_val not in ("да", "yes", "1", "true", ""):
                    continue

            # Get stock: try Остаток_расчет first, then Стартовый_остаток
            stock = to_int(safe_get(r, col_stock), 100)  # Default 100 if no stock column

            products.append(
                {
                    "sku": sku,
                    "name": safe_get(r, col_name, "Без названия"),
                    "desc_short": safe_get(r, col_desc),
                    "desc_full": safe_get(r, col_desc_full),
                    "price_rub": to_int(safe_get(r, col_price), 0),
                    "stock": stock,
                    "supplier_id": "",
                    "photo_url": convert_photo_url(safe_get(r, col_photo)),
                    "tags": safe_get(r, col_tags),
                }
            )
        return products

    # Sync versions for compatibility with existing callers
    def append_order_sync(self, order_row: list[Any]) -> None:
        self.append_values_sync("Заказы!A1", [order_row])

    def append_spisanie_rows_sync(self, rows: list[list[Any]]) -> None:
        self.append_values_sync("Списание!A1", rows)

    # Async versions for handlers
    async def append_order(self, order_row: list[Any]) -> None:
        await self.append_values("Заказы!A1", [order_row])

    async def append_spisanie_rows(self, rows: list[list[Any]]) -> None:
        await self.append_values("Списание!A1", rows)

    def get_categories(self) -> list[str]:
        """Extract unique tags/categories from all products."""
        products = self.get_products()
        tags_set = set()
        for p in products:
            tags = p.get("tags", "")
            if tags:
                for tag in tags.split(","):
                    tag = tag.strip()
                    if tag:
                        tags_set.add(tag)
        return sorted(tags_set)

    # -------------------------------------------------------------------------
    # CRM Methods (Phase 1)
    # -------------------------------------------------------------------------

    # Leads sheet columns:
    # A: user_id, B: username, C: first_seen_at, D: last_seen_at, E: stage,
    # F: orders_count, G: lifetime_value, H: last_order_id, I: consent_at,
    # J: consent_version, K: phone, L: tags, M: notes

    LEADS_COLUMNS = [
        'user_id', 'username', 'first_seen_at', 'last_seen_at', 'stage',
        'orders_count', 'lifetime_value', 'last_order_id', 'consent_at',
        'consent_version', 'phone', 'tags', 'notes'
    ]

    def _get_leads_data_sync(self) -> tuple[list[list[Any]], dict[int, int]]:
        """
        Get all leads data and build user_id -> row_index mapping.
        Returns (rows, user_id_to_row_idx).
        """
        try:
            rows = self._get_values_sync("Leads!A2:M10000")
        except HttpError as e:
            if e.resp.status == 400:
                # Sheet might not exist yet
                logger.warning("Leads sheet not found or empty")
                return [], {}
            raise

        user_id_to_row = {}
        for idx, row in enumerate(rows):
            if row and len(row) > 0:
                try:
                    uid = int(row[0])
                    user_id_to_row[uid] = idx + 2  # +2 because A2 is row 2
                except (ValueError, TypeError):
                    pass
        return rows, user_id_to_row

    async def get_lead(self, user_id: int) -> dict[str, Any] | None:
        """Get a lead by user_id."""
        rows, user_map = await asyncio.to_thread(self._get_leads_data_sync)

        if user_id not in user_map:
            return None

        row_idx = user_map[user_id] - 2  # Convert back to list index
        if row_idx < 0 or row_idx >= len(rows):
            return None

        row = rows[row_idx]
        lead = {}
        for i, col_name in enumerate(self.LEADS_COLUMNS):
            lead[col_name] = row[i] if i < len(row) else ''

        # Convert numeric fields
        try:
            lead['user_id'] = int(lead['user_id']) if lead['user_id'] else 0
            lead['orders_count'] = int(lead['orders_count']) if lead['orders_count'] else 0
            lead['lifetime_value'] = int(lead['lifetime_value']) if lead['lifetime_value'] else 0
        except (ValueError, TypeError):
            pass

        return lead

    async def upsert_lead(
        self,
        user_id: int,
        stage: str | None = None,
        *,
        username: str | None = None,
        consent_at: datetime | str | None = None,
        phone: str | None = None,
        orders_count: int | None = None,
        lifetime_value: int | None = None,
        last_order_id: str | None = None,
        tags: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """
        Update or create a lead in Leads sheet.
        Stage only goes UP (new -> engaged -> cart -> checkout -> customer -> repeat).
        Returns True if successful.
        """
        rows, user_map = await asyncio.to_thread(self._get_leads_data_sync)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if user_id in user_map:
            # Update existing lead
            row_idx = user_map[user_id]
            existing_row = rows[row_idx - 2] if (row_idx - 2) < len(rows) else []

            # Pad row to full length
            while len(existing_row) < len(self.LEADS_COLUMNS):
                existing_row.append('')

            # Get current values
            current_stage = existing_row[4] if len(existing_row) > 4 else ''
            current_orders = int(existing_row[5]) if existing_row[5] else 0
            current_ltv = int(existing_row[6]) if existing_row[6] else 0

            # Compute new stage (only goes up)
            if stage:
                current_priority = STAGE_PRIORITY.get(current_stage, 0)
                new_priority = STAGE_PRIORITY.get(stage, 0)
                if new_priority > current_priority:
                    existing_row[4] = stage

            # Update last_seen_at
            existing_row[3] = now

            # Update other fields if provided
            if username is not None:
                existing_row[1] = username
            if consent_at is not None:
                consent_str = consent_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(consent_at, datetime) else consent_at
                if not existing_row[8]:  # Don't overwrite existing consent
                    existing_row[8] = consent_str
                    existing_row[9] = 'v1'
            if phone is not None and phone:
                existing_row[10] = phone
            if orders_count is not None:
                existing_row[5] = str(orders_count)
            if lifetime_value is not None:
                existing_row[6] = str(lifetime_value)
            if last_order_id is not None:
                existing_row[7] = last_order_id
            if tags is not None:
                existing_row[11] = tags
            if notes is not None:
                existing_row[12] = notes

            # Update in Sheets
            range_a1 = f"Leads!A{row_idx}:M{row_idx}"
            await self.update_values(range_a1, [existing_row])
            logger.debug(f"Updated lead {user_id} at row {row_idx}")
            return True

        else:
            # Create new lead
            consent_str = ''
            consent_version = ''
            if consent_at is not None:
                consent_str = consent_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(consent_at, datetime) else consent_at
                consent_version = 'v1'

            new_row = [
                str(user_id),           # A: user_id
                username or '',          # B: username
                now,                     # C: first_seen_at
                now,                     # D: last_seen_at
                stage or 'new',          # E: stage
                str(orders_count or 0),  # F: orders_count
                str(lifetime_value or 0),# G: lifetime_value
                last_order_id or '',     # H: last_order_id
                consent_str,             # I: consent_at
                consent_version,         # J: consent_version
                phone or '',             # K: phone
                tags or '',              # L: tags
                notes or '',             # M: notes
            ]

            await self.append_values("Leads!A1", [new_row])
            logger.debug(f"Created new lead {user_id}")
            return True

    async def search_leads(self, query: str) -> list[dict[str, Any]]:
        """Search leads by user_id or phone."""
        rows, _ = await asyncio.to_thread(self._get_leads_data_sync)
        results = []

        query_lower = query.lower().strip()
        query_digits = ''.join(c for c in query if c.isdigit())

        for row in rows:
            if not row:
                continue

            # Match user_id
            user_id_str = str(row[0]) if row else ''
            if query_digits and query_digits in user_id_str:
                lead = dict(zip(self.LEADS_COLUMNS, row + [''] * (len(self.LEADS_COLUMNS) - len(row))))
                results.append(lead)
                continue

            # Match phone
            phone = row[10] if len(row) > 10 else ''
            phone_digits = ''.join(c for c in phone if c.isdigit())
            if query_digits and query_digits in phone_digits:
                lead = dict(zip(self.LEADS_COLUMNS, row + [''] * (len(self.LEADS_COLUMNS) - len(row))))
                results.append(lead)
                continue

            # Match username
            username = row[1] if len(row) > 1 else ''
            if query_lower and query_lower in username.lower():
                lead = dict(zip(self.LEADS_COLUMNS, row + [''] * (len(self.LEADS_COLUMNS) - len(row))))
                results.append(lead)

        return results[:20]  # Limit results

    async def update_daily_metrics(self, metrics: dict[str, Any]) -> bool:
        """
        Update or append daily metrics to MetricsDaily sheet.
        metrics: {date, visitors, engaged, cart, checkout, orders, orders_total, avg_check}
        """
        target_date = metrics.get('date', datetime.now().strftime('%Y-%m-%d'))

        try:
            rows = await self.get_values("MetricsDaily!A2:H1000")
        except HttpError:
            rows = []

        # Find existing row for this date
        row_idx = None
        for idx, row in enumerate(rows):
            if row and len(row) > 0 and row[0] == target_date:
                row_idx = idx + 2  # +2 for header and 0-indexing
                break

        avg_check = 0
        if metrics.get('orders', 0) > 0:
            avg_check = metrics.get('orders_total', 0) // metrics['orders']

        new_row = [
            target_date,
            metrics.get('visitors', 0),
            metrics.get('engaged', 0),
            metrics.get('cart', 0),
            metrics.get('checkout', 0),
            metrics.get('orders', 0),
            metrics.get('orders_total', 0),
            avg_check,
        ]

        if row_idx:
            await self.update_values(f"MetricsDaily!A{row_idx}:H{row_idx}", [new_row])
        else:
            await self.append_values("MetricsDaily!A1", [new_row])

        return True
