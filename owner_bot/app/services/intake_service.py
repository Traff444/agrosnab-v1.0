"""Intake session service."""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime

from app.cloudinary_client import cloudinary_client
from app.intake_parser import parse_intake_string
from app.models import (
    DriveUploadResult,
    IntakeSession,
    ParsedIntake,
    PhotoQualityResult,
    Product,
)
from app.photo_enhance import enhance_photo
from app.photo_quality import analyze_photo
from app.sheets import sheets_client
from app.storage import intake_session_store

logger = logging.getLogger(__name__)


@dataclass
class IntakeResult:
    """Result of completing an intake."""

    success: bool
    product: Product | None = None
    is_new: bool = False
    error: str | None = None
    photo_uploaded: bool = False
    photo_permissions_ok: bool = True


class IntakeService:
    """Service for managing intake sessions.

    Sessions are persisted in SQLite to survive bot restarts.
    """

    async def get_session(self, user_id: int) -> IntakeSession | None:
        """Get active session for user from SQLite."""
        return await intake_session_store.get(user_id)

    async def create_session(self, user_id: int) -> IntakeSession:
        """Create new intake session and save to SQLite."""
        session = IntakeSession(user_id=user_id)
        await intake_session_store.save(session)
        return session

    async def save_session(self, session: IntakeSession) -> None:
        """Save session state to SQLite."""
        await intake_session_store.save(session)

    async def clear_session(self, user_id: int) -> None:
        """Clear user's intake session from SQLite."""
        await intake_session_store.delete(user_id)

    def parse_quick_string(self, text: str) -> ParsedIntake:
        """Parse quick intake string."""
        return parse_intake_string(text)

    async def update_session_from_parsed(
        self,
        session: IntakeSession,
        parsed: ParsedIntake,
    ) -> IntakeSession:
        """Update session with parsed data and save to SQLite."""
        if parsed.name:
            session.name = parsed.name
        if parsed.price is not None:
            session.price = parsed.price
        if parsed.quantity is not None:
            session.quantity = parsed.quantity
        await intake_session_store.save(session)
        return session

    async def find_matching_products(self, name: str) -> list[Product]:
        """Find products matching the name."""
        return await sheets_client.search_products(name, limit=5)

    async def set_existing_product(
        self,
        session: IntakeSession,
        product: Product,
    ) -> IntakeSession:
        """Set session to update existing product and save to SQLite."""
        session.existing_product = product
        session.is_new_product = False
        session.sku = product.sku
        # Keep session price/quantity, use product name
        if not session.name:
            session.name = product.name
        await intake_session_store.save(session)
        return session

    async def set_new_product(self, session: IntakeSession) -> IntakeSession:
        """Set session to create new product and save to SQLite."""
        session.existing_product = None
        session.is_new_product = True
        session.sku = None
        await intake_session_store.save(session)
        return session

    async def download_and_analyze_photo(
        self,
        session: IntakeSession,
        file_path: str,
    ) -> PhotoQualityResult:
        """Analyze downloaded photo and save session."""
        result = analyze_photo(file_path)
        session.photo_quality = result
        await intake_session_store.save(session)
        return result

    async def enhance_photo(self, file_path: str) -> str:
        """Enhance photo and return new path."""
        result = enhance_photo(file_path)
        return result.path

    async def upload_photo(
        self,
        session: IntakeSession,
        file_path: str,
    ) -> DriveUploadResult:
        """Upload photo to Cloudinary and save session."""
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sku_part = session.sku or "new"
        filename = f"{sku_part}_{timestamp}.jpg"

        result = await cloudinary_client.upload_photo(file_path, filename)

        session.drive_file_id = result.file_id
        session.drive_url = result.public_url
        await intake_session_store.save(session)

        return result

    async def complete_intake(
        self,
        session: IntakeSession,
        updated_by: str = "owner_bot",
    ) -> IntakeResult:
        """Complete the intake session."""
        logger.info(
            "complete_intake: is_new=%s, name=%s, price=%s, qty=%s, photo_url=%s",
            session.is_new_product,
            session.name,
            session.price,
            session.quantity,
            session.drive_url,
        )
        if session.is_new_product:
            return await self._create_new_product(session, updated_by)
        else:
            return await self._update_existing_product(session, updated_by)

    async def _create_new_product(
        self,
        session: IntakeSession,
        updated_by: str,
    ) -> IntakeResult:
        """Create new product from session."""
        logger.info("_create_new_product: starting")
        if not session.name or session.price is None or session.quantity is None:
            logger.warning(
                "_create_new_product: missing fields - name=%s, price=%s, qty=%s",
                session.name,
                session.price,
                session.quantity,
            )
            return IntakeResult(
                success=False,
                error="Не заполнены обязательные поля: название, цена, количество",
            )

        try:
            logger.info(
                "_create_new_product: calling sheets_client.create_product(%s, %s, %s)",
                session.name,
                session.price,
                session.quantity,
            )
            product = await sheets_client.create_product(
                name=session.name,
                price=session.price,
                quantity=session.quantity,
                photo_url=session.drive_url or "",
                updated_by=updated_by,
            )
            logger.info(
                "_create_new_product: success! SKU=%s, row=%s",
                product.sku,
                product.row_number,
            )

            # Log intake to "Внесение" sheet
            if session.quantity > 0:
                actor_username = updated_by.replace("tg:", "")
                intake_result = await sheets_client.apply_intake(
                    row_number=product.row_number,
                    qty=session.quantity,
                    stock_before=0,  # New product starts at 0
                    stock_after=session.quantity,
                    reason="new_product",
                    actor_id=session.user_id,
                    actor_username=actor_username,
                    operation_id=secrets.token_hex(8),
                    note="Создание нового товара",
                )
                if not intake_result.ok:
                    logger.warning(
                        "_create_new_product: failed to log intake: %s",
                        intake_result.error,
                    )

            return IntakeResult(
                success=True,
                product=product,
                is_new=True,
                photo_uploaded=bool(session.drive_url),
            )
        except Exception as e:
            logger.exception("_create_new_product: failed with exception")
            return IntakeResult(
                success=False,
                error=f"Ошибка создания товара: {e}",
            )

    async def _update_existing_product(
        self,
        session: IntakeSession,
        updated_by: str,
    ) -> IntakeResult:
        """Update existing product from session."""
        logger.info("_update_existing_product: starting")
        if not session.existing_product:
            logger.warning("_update_existing_product: no existing_product set")
            return IntakeResult(
                success=False,
                error="Товар не выбран",
            )

        if session.quantity is None:
            logger.warning("_update_existing_product: quantity is None")
            return IntakeResult(
                success=False,
                error="Не указано количество",
            )

        try:
            logger.info(
                "_update_existing_product: updating stock for SKU=%s, delta=%d",
                session.existing_product.sku,
                session.quantity,
            )
            # Update stock
            product = await sheets_client.update_product_stock(
                product=session.existing_product,
                quantity_delta=session.quantity,
                updated_by=updated_by,
            )
            logger.info("_update_existing_product: stock updated, new_stock=%d", product.stock)

            # Log intake to "Внесение" sheet
            if session.quantity > 0:
                stock_before = session.existing_product.stock
                stock_after = product.stock
                actor_username = updated_by.replace("tg:", "")
                intake_result = await sheets_client.apply_intake(
                    row_number=session.existing_product.row_number,
                    qty=session.quantity,
                    stock_before=stock_before,
                    stock_after=stock_after,
                    reason="intake",
                    actor_id=session.user_id,
                    actor_username=actor_username,
                    operation_id=secrets.token_hex(8),
                    note="",
                )
                if not intake_result.ok:
                    logger.warning(
                        "_update_existing_product: failed to log intake: %s",
                        intake_result.error,
                    )

            # Update photo if provided
            photo_permissions_ok = True
            if session.drive_url:
                logger.info("_update_existing_product: updating photo URL")
                product = await sheets_client.update_product_photo(
                    product=product,
                    photo_url=session.drive_url,
                    updated_by=updated_by,
                )
                logger.info("_update_existing_product: photo URL updated")

            return IntakeResult(
                success=True,
                product=product,
                is_new=False,
                photo_uploaded=bool(session.drive_url),
                photo_permissions_ok=photo_permissions_ok,
            )
        except Exception as e:
            logger.exception("_update_existing_product: failed with exception")
            return IntakeResult(
                success=False,
                error=f"Ошибка обновления товара: {e}",
            )

    def format_session_preview(self, session: IntakeSession) -> str:
        """Format session as preview card."""
        lines = ["📋 **Предпросмотр прихода**", ""]

        if session.is_new_product:
            lines.append("🆕 **Новый товар**")
        else:
            lines.append("📦 **Обновление существующего**")
            if session.existing_product:
                lines.append(f"SKU: `{session.existing_product.sku}`")

        lines.append("")

        if session.name:
            lines.append(f"📦 Название: {session.name}")
        if session.price is not None:
            lines.append(f"💰 Цена: {session.price:.2f} ₽")
        if session.quantity is not None:
            lines.append(f"📊 Количество: +{session.quantity} шт.")

        if session.existing_product and session.quantity:
            old_stock = session.existing_product.stock
            new_stock = old_stock + session.quantity
            lines.append(f"📈 Остаток: {old_stock} → {new_stock}")

        if session.drive_url:
            lines.append("📷 Фото: загружено")
        else:
            lines.append("📷 Фото: нет")

        return "\n".join(lines)

    def compute_fingerprint(self, session: IntakeSession) -> str:
        """Compute idempotency fingerprint."""
        return session.compute_fingerprint()


# Global service instance
intake_service = IntakeService()
