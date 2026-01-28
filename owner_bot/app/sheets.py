"""Google Sheets client with dynamic column mapping."""

import logging
import secrets
from datetime import datetime
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.models import Product

logger = logging.getLogger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

REQUIRED_COLUMNS = ["SKU", "Наименование", "Цена_руб", "Остаток_расчет", "Фото_URL", "Активен"]
OPTIONAL_COLUMNS = ["Теги", "Описание_кратко", "Описание_полное", "Стартовый_остаток", "Внесено_всего", "Списано_всего", "Поставщик_ID", "last_intake_at", "last_intake_qty", "last_updated_by"]

# Column aliases for code compatibility
COL_ALIASES = {
    "Цена": "Цена_руб",
    "Остаток": "Остаток_расчет",
    "Фото": "Фото_URL",
}


class SheetsClient:
    """Google Sheets client with dynamic column mapping."""

    def __init__(self):
        self._service = None
        self._col_map: dict[str, int] = {}
        self._headers: list[str] = []
        self._sheet_name = "Склад"

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
        """Convert 0-based index to column letter (A, B, ..., Z, AA, AB, ...)."""
        result = ""
        while index >= 0:
            result = chr(index % 26 + ord("A")) + result
            index = index // 26 - 1
        return result

    def _col_idx(self, name: str) -> int:
        """Get column index by name, supporting aliases."""
        # Try direct name first
        if name in self._col_map:
            return self._col_map[name]
        # Try alias
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

        # Verify required columns exist
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

    async def get_all_products(self) -> list[Product]:
        """Get all products from the sheet."""
        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!A2:Z",
            )
            .execute()
        )

        rows = result.get("values", [])
        products = []

        for idx, row in enumerate(rows):
            row_data = self._row_to_dict(row)
            if row_data.get("SKU"):  # Skip empty rows
                products.append(Product.from_row(idx + 2, row_data, self._col_map))

        return products

    async def find_product_by_sku(self, sku: str) -> Product | None:
        """Find product by exact SKU match."""
        products = await self.get_all_products()
        for product in products:
            if product.sku == sku:
                return product
        return None

    async def search_products(self, query: str, limit: int = 5) -> list[Product]:
        """Search products by name (contains) or SKU (exact)."""
        products = await self.get_all_products()
        query_lower = query.lower()

        # First try exact SKU match
        for product in products:
            if product.sku.lower() == query_lower:
                return [product]

        # Then search by name
        matches = [p for p in products if query_lower in p.name.lower()]
        return matches[:limit]

    def _generate_sku(self) -> str:
        """Generate unique SKU in format PRD-YYYYMMDD-XXXX."""
        date_part = datetime.now().strftime("%Y%m%d")
        random_part = secrets.token_hex(2).upper()
        return f"PRD-{date_part}-{random_part}"

    async def create_product(
        self,
        name: str,
        price: float,
        quantity: int,
        photo_url: str = "",
        description: str = "",
        tags: str = "",
        updated_by: str = "owner_bot",
    ) -> Product:
        """Create a new product in the sheet."""
        settings = get_settings()
        sku = self._generate_sku()
        now = datetime.now().isoformat()

        # Build row based on column map
        row = [""] * (max(self._col_map.values()) + 1)

        row[self._col_idx("SKU")] = sku
        row[self._col_idx("Наименование")] = name
        row[self._col_idx("Цена")] = price
        row[self._col_idx("Остаток")] = quantity
        row[self._col_idx("Фото")] = photo_url
        row[self._col_idx("Активен")] = "TRUE"

        if "Теги" in self._col_map:
            row[self._col_map["Теги"]] = tags
        if "Описание_кратко" in self._col_map:
            row[self._col_map["Описание_кратко"]] = description
        if "last_intake_at" in self._col_map:
            row[self._col_map["last_intake_at"]] = now
        if "last_intake_qty" in self._col_map:
            row[self._col_map["last_intake_qty"]] = quantity
        if "last_updated_by" in self._col_map:
            row[self._col_map["last_updated_by"]] = updated_by

        result = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!A:A",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )

        # Extract new row number from response
        updated_range = result.get("updates", {}).get("updatedRange", "")
        # Format: "Склад!A123:Z123"
        row_num = int(updated_range.split("!")[1].split(":")[0][1:])

        return Product(
            row_number=row_num,
            sku=sku,
            name=name,
            price=price,
            stock=quantity,
            photo_url=photo_url,
            description=description,
            tags=tags,
            active=True,
            last_intake_at=datetime.now(),
            last_intake_qty=quantity,
            last_updated_by=updated_by,
        )

    async def update_product_stock(
        self,
        product: Product,
        quantity_delta: int,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product stock by adding quantity_delta."""
        settings = get_settings()
        new_stock = product.stock + quantity_delta
        now = datetime.now().isoformat()

        updates = []

        # Update Остаток
        stock_col = self._col_letter(self._col_idx("Остаток"))
        updates.append({
            "range": f"{self._sheet_name}!{stock_col}{product.row_number}",
            "values": [[new_stock]],
        })

        # Update service fields if they exist
        if "last_intake_at" in self._col_map:
            col = self._col_letter(self._col_map["last_intake_at"])
            updates.append({
                "range": f"{self._sheet_name}!{col}{product.row_number}",
                "values": [[now]],
            })

        if "last_intake_qty" in self._col_map:
            col = self._col_letter(self._col_map["last_intake_qty"])
            updates.append({
                "range": f"{self._sheet_name}!{col}{product.row_number}",
                "values": [[quantity_delta]],
            })

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append({
                "range": f"{self._sheet_name}!{col}{product.row_number}",
                "values": [[updated_by]],
            })

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=new_stock,
            photo_url=product.photo_url,
            description=product.description,
            tags=product.tags,
            active=product.active,
            last_intake_at=datetime.now(),
            last_intake_qty=quantity_delta,
            last_updated_by=updated_by,
        )

    async def update_product_photo(
        self,
        product: Product,
        photo_url: str,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product photo URL."""
        settings = get_settings()

        photo_col = self._col_letter(self._col_idx("Фото"))
        updates = [{
            "range": f"{self._sheet_name}!{photo_col}{product.row_number}",
            "values": [[photo_url]],
        }]

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append({
                "range": f"{self._sheet_name}!{col}{product.row_number}",
                "values": [[updated_by]],
            })

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=product.stock,
            photo_url=photo_url,
            description=product.description,
            tags=product.tags,
            active=product.active,
            last_intake_at=product.last_intake_at,
            last_intake_qty=product.last_intake_qty,
            last_updated_by=updated_by,
        )

    async def update_product_active(
        self,
        product: Product,
        active: bool,
        updated_by: str = "owner_bot",
    ) -> Product:
        """Update product active status."""
        settings = get_settings()

        active_col = self._col_letter(self._col_map["Активен"])
        updates = [{
            "range": f"{self._sheet_name}!{active_col}{product.row_number}",
            "values": [["TRUE" if active else "FALSE"]],
        }]

        if "last_updated_by" in self._col_map:
            col = self._col_letter(self._col_map["last_updated_by"])
            updates.append({
                "range": f"{self._sheet_name}!{col}{product.row_number}",
                "values": [[updated_by]],
            })

        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        ).execute()

        return Product(
            row_number=product.row_number,
            sku=product.sku,
            name=product.name,
            price=product.price,
            stock=product.stock,
            photo_url=product.photo_url,
            description=product.description,
            tags=product.tags,
            active=active,
            last_intake_at=product.last_intake_at,
            last_intake_qty=product.last_intake_qty,
            last_updated_by=updated_by,
        )

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

    # -------------------------------------------------------------------------
    # CRM Methods (Phase 2)
    # -------------------------------------------------------------------------

    LEADS_COLUMNS = [
        'user_id', 'username', 'first_seen_at', 'last_seen_at', 'stage',
        'orders_count', 'lifetime_value', 'last_order_id', 'consent_at',
        'consent_version', 'phone', 'tags', 'notes'
    ]

    async def get_leads(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent leads from Leads sheet."""
        settings = get_settings()

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=settings.google_sheets_id,
                    range="Leads!A2:M10000",
                )
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to get leads: {e}")
            from app.monitoring import capture_exception
            capture_exception(e, {"method": "get_leads"})
            return []

        rows = result.get("values", [])
        leads = []

        for row in rows:
            if not row:
                continue
            lead = {}
            for i, col_name in enumerate(self.LEADS_COLUMNS):
                lead[col_name] = row[i] if i < len(row) else ''
            leads.append(lead)

        # Sort by last_seen_at descending and limit
        leads.sort(key=lambda x: x.get('last_seen_at', ''), reverse=True)
        return leads[:limit]

    async def get_lead_by_user_id(self, user_id: int) -> dict[str, Any] | None:
        """Get a specific lead by user_id."""
        leads = await self.get_leads(limit=10000)
        for lead in leads:
            try:
                if int(lead.get('user_id', 0)) == user_id:
                    return lead
            except (ValueError, TypeError):
                continue
        return None

    async def search_leads(self, query: str) -> list[dict[str, Any]]:
        """Search leads by user_id, phone, or username."""
        leads = await self.get_leads(limit=10000)
        results = []

        query_lower = query.lower().strip()
        query_digits = ''.join(c for c in query if c.isdigit())

        for lead in leads:
            # Match user_id
            user_id_str = str(lead.get('user_id', ''))
            if query_digits and query_digits in user_id_str:
                results.append(lead)
                continue

            # Match phone
            phone = lead.get('phone', '')
            phone_digits = ''.join(c for c in phone if c.isdigit())
            if query_digits and len(query_digits) >= 4 and query_digits in phone_digits:
                results.append(lead)
                continue

            # Match username
            username = lead.get('username', '')
            if query_lower and query_lower in username.lower():
                results.append(lead)

        return results[:20]

    async def update_lead_notes(self, user_id: int, notes: str) -> bool:
        """Update notes for a lead."""
        settings = get_settings()

        # Find lead row
        leads = await self.get_leads(limit=10000)
        row_idx = None
        for idx, lead in enumerate(leads):
            try:
                if int(lead.get('user_id', 0)) == user_id:
                    row_idx = idx + 2  # +2 for header and 0-indexing
                    break
            except (ValueError, TypeError):
                continue

        if row_idx is None:
            return False

        # Update notes column (M)
        self.service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_id,
            range=f"Leads!M{row_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [[notes]]},
        ).execute()

        return True

    async def update_lead_tags(self, user_id: int, tags: str) -> bool:
        """Update tags for a lead."""
        settings = get_settings()

        # Find lead row
        leads = await self.get_leads(limit=10000)
        row_idx = None
        for idx, lead in enumerate(leads):
            try:
                if int(lead.get('user_id', 0)) == user_id:
                    row_idx = idx + 2
                    break
            except (ValueError, TypeError):
                continue

        if row_idx is None:
            return False

        # Update tags column (L)
        self.service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_id,
            range=f"Leads!L{row_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [[tags]]},
        ).execute()

        return True

    async def get_funnel_stats(self) -> dict[str, int]:
        """Get funnel statistics from leads."""
        leads = await self.get_leads(limit=10000)

        stats = {
            'total': len(leads),
            'new': 0,
            'engaged': 0,
            'cart': 0,
            'checkout': 0,
            'customer': 0,
            'repeat': 0,
        }

        for lead in leads:
            stage = lead.get('stage', 'new')
            if stage in stats:
                stats[stage] += 1

        return stats

    async def get_orders_summary(self) -> dict[str, Any]:
        """Get today's orders summary from Заказы sheet."""
        settings = get_settings()
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=settings.google_sheets_id,
                    range="Заказы!A2:J1000",
                )
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to get orders summary: {e}")
            from app.monitoring import capture_exception
            capture_exception(e, {"method": "get_orders_summary"})
            return {'orders_count': 0, 'orders_total': 0, 'orders_today': []}

        rows = result.get("values", [])
        today_orders = []
        total = 0

        for row in rows:
            if len(row) > 1:
                order_date = row[1] if len(row) > 1 else ''
                if today in order_date:
                    order_total = 0
                    if len(row) > 5:
                        try:
                            order_total = int(float(str(row[5]).replace(' ', '').replace(',', '.')))
                        except (ValueError, TypeError):
                            pass
                    today_orders.append({
                        'order_id': row[0] if row else '',
                        'date': order_date,
                        'user_id': row[2] if len(row) > 2 else '',
                        'phone': row[3] if len(row) > 3 else '',
                        'status': row[4] if len(row) > 4 else '',
                        'total': order_total,
                    })
                    total += order_total

        return {
            'orders_count': len(today_orders),
            'orders_total': total,
            'orders_today': today_orders,
        }


# Global client instance
sheets_client = SheetsClient()
