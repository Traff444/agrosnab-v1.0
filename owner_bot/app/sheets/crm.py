"""CRM operations for Google Sheets (Leads, Orders)."""

import contextlib
import logging
from datetime import datetime
from typing import Any

from ..config import get_settings
from .client import BaseSheetsClient
from .constants import LEADS_COLUMNS

logger = logging.getLogger(__name__)


class CRMOperationsMixin:
    """Mixin for CRM operations (leads, orders)."""

    async def get_leads(self: BaseSheetsClient, limit: int = 50) -> list[dict[str, Any]]:
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
            logger.error("Failed to get leads: %s", e)
            from ..monitoring import capture_exception

            capture_exception(e, {"method": "get_leads"})
            return []

        rows = result.get("values", [])
        leads = []

        for row in rows:
            if not row:
                continue
            lead = {}
            for i, col_name in enumerate(LEADS_COLUMNS):
                lead[col_name] = row[i] if i < len(row) else ""
            leads.append(lead)

        leads.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
        return leads[:limit]

    async def get_lead_by_user_id(
        self: BaseSheetsClient, user_id: int
    ) -> dict[str, Any] | None:
        """Get a specific lead by user_id."""
        leads = await self.get_leads(limit=10000)
        for lead in leads:
            try:
                if int(lead.get("user_id", 0)) == user_id:
                    return lead
            except (ValueError, TypeError):
                continue
        return None

    async def search_leads(
        self: BaseSheetsClient, query: str
    ) -> list[dict[str, Any]]:
        """Search leads by user_id, phone, or username."""
        leads = await self.get_leads(limit=10000)
        results = []

        query_lower = query.lower().strip()
        query_digits = "".join(c for c in query if c.isdigit())

        for lead in leads:
            user_id_str = str(lead.get("user_id", ""))
            if query_digits and query_digits in user_id_str:
                results.append(lead)
                continue

            phone = lead.get("phone", "")
            phone_digits = "".join(c for c in phone if c.isdigit())
            if query_digits and len(query_digits) >= 4 and query_digits in phone_digits:
                results.append(lead)
                continue

            username = lead.get("username", "")
            if query_lower and query_lower in username.lower():
                results.append(lead)

        return results[:20]

    async def update_lead_notes(
        self: BaseSheetsClient, user_id: int, notes: str
    ) -> bool:
        """Update notes for a lead."""
        settings = get_settings()

        leads = await self.get_leads(limit=10000)
        row_idx = None
        for idx, lead in enumerate(leads):
            try:
                if int(lead.get("user_id", 0)) == user_id:
                    row_idx = idx + 2
                    break
            except (ValueError, TypeError):
                continue

        if row_idx is None:
            return False

        self.service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_id,
            range=f"Leads!M{row_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [[notes]]},
        ).execute()

        return True

    async def update_lead_tags(
        self: BaseSheetsClient, user_id: int, tags: str
    ) -> bool:
        """Update tags for a lead."""
        settings = get_settings()

        leads = await self.get_leads(limit=10000)
        row_idx = None
        for idx, lead in enumerate(leads):
            try:
                if int(lead.get("user_id", 0)) == user_id:
                    row_idx = idx + 2
                    break
            except (ValueError, TypeError):
                continue

        if row_idx is None:
            return False

        self.service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_id,
            range=f"Leads!L{row_idx}",
            valueInputOption="USER_ENTERED",
            body={"values": [[tags]]},
        ).execute()

        return True

    async def get_funnel_stats(self: BaseSheetsClient) -> dict[str, int]:
        """Get funnel statistics from leads."""
        leads = await self.get_leads(limit=10000)

        stats = {
            "total": len(leads),
            "new": 0,
            "engaged": 0,
            "cart": 0,
            "checkout": 0,
            "customer": 0,
            "repeat": 0,
        }

        for lead in leads:
            stage = lead.get("stage", "new")
            if stage in stats:
                stats[stage] += 1

        return stats

    async def get_orders_summary(self: BaseSheetsClient) -> dict[str, Any]:
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
            logger.error("Failed to get orders summary: %s", e)
            from ..monitoring import capture_exception

            capture_exception(e, {"method": "get_orders_summary"})
            return {"orders_count": 0, "orders_total": 0, "orders_today": []}

        rows = result.get("values", [])
        today_orders = []
        total = 0

        for row in rows:
            if len(row) > 1:
                order_date = row[1] if len(row) > 1 else ""
                if today in order_date:
                    order_total = 0
                    if len(row) > 5:
                        with contextlib.suppress(ValueError, TypeError):
                            order_total = int(
                                float(str(row[5]).replace(" ", "").replace(",", "."))
                            )
                    today_orders.append(
                        {
                            "order_id": row[0] if row else "",
                            "date": order_date,
                            "user_id": row[2] if len(row) > 2 else "",
                            "phone": row[3] if len(row) > 3 else "",
                            "status": row[4] if len(row) > 4 else "",
                            "total": order_total,
                        }
                    )
                    total += order_total

        return {
            "orders_count": len(today_orders),
            "orders_total": total,
            "orders_today": today_orders,
        }
