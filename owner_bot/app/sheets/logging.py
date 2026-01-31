"""Stock logging operations for Google Sheets (Внесение/Списание)."""

import logging
import secrets
from datetime import datetime

from ..config import get_settings
from ..models import Product
from .client import BaseSheetsClient
from .constants import DEDUP_LOOKBACK_ROWS, LOG_COLUMNS
from .models import StockOperationResult

logger = logging.getLogger(__name__)


class LoggingOperationsMixin:
    """Mixin for stock logging operations."""

    async def _ensure_sheet_exists(self: BaseSheetsClient, sheet_name: str) -> bool:
        """Ensure a sheet exists, create if missing. Returns True on success."""
        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .get(spreadsheetId=settings.google_sheets_id)
            .execute()
        )

        sheets = [s["properties"]["title"] for s in result.get("sheets", [])]

        if sheet_name in sheets:
            return True

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()

        return True

    async def ensure_log_columns(
        self: BaseSheetsClient, sheet_name: str
    ) -> dict[str, int]:
        """
        Ensure log sheet has all required columns (self-heal).
        Returns column mapping {col_name: index}.
        Cached until clear_log_column_cache is called.
        """
        if sheet_name in self._log_col_map_cache:
            return self._log_col_map_cache[sheet_name]

        settings = get_settings()

        await self._ensure_sheet_exists(sheet_name)

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{sheet_name}!1:1",
            )
            .execute()
        )

        existing_headers = (
            result.get("values", [[]])[0] if result.get("values") else []
        )

        col_map = {header: idx for idx, header in enumerate(existing_headers)}

        missing = [col for col in LOG_COLUMNS if col not in col_map]

        if missing:
            if not existing_headers:
                self.service.spreadsheets().values().update(
                    spreadsheetId=settings.google_sheets_id,
                    range=f"{sheet_name}!A1",
                    valueInputOption="RAW",
                    body={"values": [LOG_COLUMNS]},
                ).execute()
                col_map = {col: idx for idx, col in enumerate(LOG_COLUMNS)}
            else:
                start_col = self._col_letter(len(existing_headers))
                self.service.spreadsheets().values().update(
                    spreadsheetId=settings.google_sheets_id,
                    range=f"{sheet_name}!{start_col}1",
                    valueInputOption="RAW",
                    body={"values": [missing]},
                ).execute()

                for i, col in enumerate(missing):
                    col_map[col] = len(existing_headers) + i

        self._log_col_map_cache[sheet_name] = col_map
        return col_map

    def clear_log_column_cache(self: BaseSheetsClient, sheet_name: str) -> None:
        """Clear cached column mapping for a log sheet."""
        self._log_col_map_cache.pop(sheet_name, None)

    async def _check_operation_exists(
        self: BaseSheetsClient, sheet_name: str, operation_id: str
    ) -> bool:
        """Check if operation_id exists in recent rows (deduplication)."""
        settings = get_settings()

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{sheet_name}!A2:C{DEDUP_LOOKBACK_ROWS + 1}",
            )
            .execute()
        )

        rows = result.get("values", [])
        return any(len(row) > 1 and row[1] == operation_id for row in rows)

    async def append_log_entry(
        self: BaseSheetsClient,
        sheet_name: str,
        sku: str,
        name: str,
        qty: int,
        stock_before: int,
        stock_after: int,
        reason: str,
        source: str,
        actor_id: int,
        actor_username: str,
        operation_id: str,
        note: str = "",
    ) -> bool:
        """Append a log entry to the specified sheet. Returns True on success."""
        settings = get_settings()

        col_map = await self.ensure_log_columns(sheet_name)

        row_data = [""] * len(col_map)
        row_data[col_map["date"]] = datetime.now().isoformat()
        row_data[col_map["operation_id"]] = operation_id
        row_data[col_map["sku"]] = sku
        row_data[col_map["name"]] = name
        row_data[col_map["qty"]] = qty
        row_data[col_map["stock_before"]] = stock_before
        row_data[col_map["stock_after"]] = stock_after
        row_data[col_map["reason"]] = reason
        row_data[col_map["source"]] = source
        row_data[col_map["actor_id"]] = actor_id
        row_data[col_map["actor_username"]] = actor_username
        row_data[col_map["note"]] = note

        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=settings.google_sheets_id,
                range=f"{sheet_name}!A:A",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row_data]},
            ).execute()
            return True
        except Exception as e:
            logger.error("Failed to append log entry to %s: %s", sheet_name, e)
            return False

    async def _increment_total_column(
        self: BaseSheetsClient, row_number: int, column_name: str, delta: int
    ) -> None:
        """Increment a total column (e.g., Списано_всего) by delta."""
        if column_name not in self._col_map:
            return

        settings = get_settings()
        col_letter = self._col_letter(self._col_map[column_name])

        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=settings.google_sheets_id,
                range=f"{self._sheet_name}!{col_letter}{row_number}",
            )
            .execute()
        )

        current_value = 0
        values = result.get("values", [[]])
        if values and values[0]:
            try:
                current_value = int(values[0][0] or 0)
            except (ValueError, TypeError):
                current_value = 0

        new_value = current_value + delta

        self.service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_id,
            range=f"{self._sheet_name}!{col_letter}{row_number}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_value]]},
        ).execute()

    async def apply_intake(
        self: BaseSheetsClient,
        row_number: int,
        qty: int,
        stock_before: int,
        stock_after: int,
        reason: str,
        actor_id: int,
        actor_username: str,
        operation_id: str | None = None,
        note: str = "",
    ) -> StockOperationResult:
        """
        Log intake operation to "Внесение" sheet and increment Внесено_всего.

        Note: This method only logs the operation. Stock updates should be
        performed separately using update_product_stock() or create_product().
        """
        if operation_id is None:
            operation_id = secrets.token_hex(8)

        if qty <= 0:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_after,
                operation_id=operation_id,
                error="Количество должно быть больше 0",
            )

        product = await self.get_product_by_row(row_number)
        if not product:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_after,
                operation_id=operation_id,
                error="Товар не найден",
            )

        await self.ensure_log_columns("Внесение")
        if await self._check_operation_exists("Внесение", operation_id):
            return StockOperationResult(
                ok=True,
                stock_before=stock_before,
                stock_after=stock_after,
                operation_id=operation_id,
            )

        log_success = await self.append_log_entry(
            sheet_name="Внесение",
            sku=product.sku,
            name=product.name,
            qty=qty,
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason,
            source="owner_intake",
            actor_id=actor_id,
            actor_username=actor_username,
            operation_id=operation_id,
            note=note,
        )

        if not log_success:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error="Не удалось записать в журнал",
            )

        try:
            await self._increment_total_column(row_number, "Внесено_всего", qty)
        except Exception as e:
            logger.error("Failed to increment Внесено_всего: %s", e)

        return StockOperationResult(
            ok=True,
            stock_before=stock_before,
            stock_after=stock_after,
            operation_id=operation_id,
        )

    async def apply_writeoff(
        self: BaseSheetsClient,
        row_number: int,
        qty: int,
        reason: str,
        actor_id: int,
        actor_username: str,
        note: str = "",
        operation_id: str | None = None,
    ) -> StockOperationResult:
        """Apply writeoff: decrease stock and log to 'Списание'."""
        if operation_id is None:
            operation_id = secrets.token_hex(8)

        if qty <= 0:
            return StockOperationResult(
                ok=False,
                stock_before=0,
                stock_after=0,
                operation_id=operation_id,
                error="Количество должно быть больше 0",
            )

        product = await self.get_product_by_row(row_number)
        if not product:
            return StockOperationResult(
                ok=False,
                stock_before=0,
                stock_after=0,
                operation_id=operation_id,
                error="Товар не найден",
            )

        stock_before = product.stock

        if qty > stock_before:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error=f"Недостаточно товара. Остаток: {stock_before}",
            )

        stock_after = stock_before - qty

        await self.ensure_log_columns("Списание")
        if await self._check_operation_exists("Списание", operation_id):
            await self.update_product_stock(product, -qty, f"tg:{actor_username}")
            await self._increment_total_column(row_number, "Списано_всего", qty)
            return StockOperationResult(
                ok=True,
                stock_before=stock_before,
                stock_after=stock_after,
                operation_id=operation_id,
            )

        log_success = await self.append_log_entry(
            sheet_name="Списание",
            sku=product.sku,
            name=product.name,
            qty=qty,
            stock_before=stock_before,
            stock_after=stock_after,
            reason=reason,
            source="owner_manual",
            actor_id=actor_id,
            actor_username=actor_username,
            operation_id=operation_id,
            note=note or "pending_stock_update",
        )

        if not log_success:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error="Не удалось записать в журнал",
            )

        try:
            await self.update_product_stock(product, -qty, f"tg:{actor_username}")
            await self._increment_total_column(row_number, "Списано_всего", qty)
        except Exception as e:
            logger.error("Failed to update stock after writeoff log: %s", e)
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error=f"Запись в журнал создана, но обновление остатка не удалось: {e}",
            )

        return StockOperationResult(
            ok=True,
            stock_before=stock_before,
            stock_after=stock_after,
            operation_id=operation_id,
        )

    async def apply_correction(
        self: BaseSheetsClient,
        row_number: int,
        new_stock: int,
        reason: str,
        actor_id: int,
        actor_username: str,
        operation_id: str | None = None,
    ) -> StockOperationResult:
        """
        Apply stock correction.
        delta < 0: log to 'Списание' (source=owner_correction)
        delta > 0: log to 'Внесение' (source=owner_correction)
        delta == 0: no log, just return ok
        """
        if operation_id is None:
            operation_id = secrets.token_hex(8)

        if new_stock < 0:
            return StockOperationResult(
                ok=False,
                stock_before=0,
                stock_after=0,
                operation_id=operation_id,
                error="Остаток не может быть отрицательным",
            )

        product = await self.get_product_by_row(row_number)
        if not product:
            return StockOperationResult(
                ok=False,
                stock_before=0,
                stock_after=0,
                operation_id=operation_id,
                error="Товар не найден",
            )

        stock_before = product.stock
        delta = new_stock - stock_before

        if delta == 0:
            return StockOperationResult(
                ok=True,
                stock_before=stock_before,
                stock_after=new_stock,
                operation_id=operation_id,
            )

        if delta < 0:
            sheet_name = "Списание"
            qty = abs(delta)
            total_column = "Списано_всего"
        else:
            sheet_name = "Внесение"
            qty = delta
            total_column = "Внесено_всего"

        log_success = await self.append_log_entry(
            sheet_name=sheet_name,
            sku=product.sku,
            name=product.name,
            qty=qty,
            stock_before=stock_before,
            stock_after=new_stock,
            reason=f"correction:{reason}",
            source="owner_correction",
            actor_id=actor_id,
            actor_username=actor_username,
            operation_id=operation_id,
            note="",
        )

        if not log_success:
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error="Не удалось записать в журнал",
            )

        try:
            await self.update_product_stock(product, delta, f"tg:{actor_username}")
            await self._increment_total_column(row_number, total_column, qty)
        except Exception as e:
            logger.error("Failed to update stock after correction log: %s", e)
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=stock_before,
                operation_id=operation_id,
                error=f"Запись в журнал создана, но обновление остатка не удалось: {e}",
            )

        return StockOperationResult(
            ok=True,
            stock_before=stock_before,
            stock_after=new_stock,
            operation_id=operation_id,
        )

    async def apply_archive_zero_out(
        self: BaseSheetsClient,
        row_number: int,
        actor_id: int,
        actor_username: str,
        operation_id: str | None = None,
    ) -> StockOperationResult:
        """Archive with zero out: writeoff remaining stock + deactivate."""
        if operation_id is None:
            operation_id = secrets.token_hex(8)

        product = await self.get_product_by_row(row_number)
        if not product:
            return StockOperationResult(
                ok=False,
                stock_before=0,
                stock_after=0,
                operation_id=operation_id,
                error="Товар не найден",
            )

        stock_before = product.stock

        if stock_before > 0:
            log_success = await self.append_log_entry(
                sheet_name="Списание",
                sku=product.sku,
                name=product.name,
                qty=stock_before,
                stock_before=stock_before,
                stock_after=0,
                reason="archive:zero_out",
                source="owner_manual",
                actor_id=actor_id,
                actor_username=actor_username,
                operation_id=operation_id,
                note="",
            )

            if not log_success:
                return StockOperationResult(
                    ok=False,
                    stock_before=stock_before,
                    stock_after=stock_before,
                    operation_id=operation_id,
                    error="Не удалось записать в журнал",
                )

            try:
                await self.update_product_stock(
                    product, -stock_before, f"tg:{actor_username}"
                )
                await self._increment_total_column(
                    row_number, "Списано_всего", stock_before
                )
            except Exception as e:
                logger.error("Failed to zero out stock: %s", e)
                return StockOperationResult(
                    ok=False,
                    stock_before=stock_before,
                    stock_after=stock_before,
                    operation_id=operation_id,
                    error=f"Не удалось обнулить остаток: {e}",
                )

        try:
            updated_product = Product(
                row_number=product.row_number,
                sku=product.sku,
                name=product.name,
                price=product.price,
                stock=0,
                photo_url=product.photo_url,
                description=product.description,
                tags=product.tags,
                active=product.active,
                last_intake_at=product.last_intake_at,
                last_intake_qty=product.last_intake_qty,
                last_updated_by=product.last_updated_by,
            )
            await self.update_product_active(
                product=updated_product,
                active=False,
                updated_by=f"tg:{actor_username}",
            )
        except Exception as e:
            logger.error("Failed to deactivate product: %s", e)
            return StockOperationResult(
                ok=False,
                stock_before=stock_before,
                stock_after=0,
                operation_id=operation_id,
                error=f"Не удалось деактивировать товар: {e}",
            )

        return StockOperationResult(
            ok=True,
            stock_before=stock_before,
            stock_after=0,
            operation_id=operation_id,
        )
