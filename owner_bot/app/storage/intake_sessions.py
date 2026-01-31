"""SQLite storage for intake sessions.

Persists IntakeSession data across bot restarts.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from app.models import IntakeSession

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = "data/owner_bot.db"
# Session TTL (24 hours)
SESSION_TTL_HOURS = 24


class IntakeSessionStore:
    """SQLite-backed storage for intake sessions."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure database and table exist."""
        if self._initialized:
            return

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS intake_sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_intake_sessions_updated
                ON intake_sessions(updated_at)
            """)
            await db.commit()

        self._initialized = True

    def _serialize_session(self, session: IntakeSession) -> str:
        """Serialize IntakeSession to JSON string."""
        data: dict[str, Any] = {
            "user_id": session.user_id,
            "name": session.name,
            "price": session.price,
            "quantity": session.quantity,
            "sku": session.sku,
            "is_new_product": session.is_new_product,
            "photo_file_id": session.photo_file_id,
            "drive_file_id": session.drive_file_id,
            "drive_url": session.drive_url,
            "fingerprint": session.fingerprint,
            "created_at": session.created_at.isoformat(),
        }

        # Serialize existing_product if present
        if session.existing_product:
            data["existing_product"] = {
                "row_number": session.existing_product.row_number,
                "sku": session.existing_product.sku,
                "name": session.existing_product.name,
                "price": session.existing_product.price,
                "stock": session.existing_product.stock,
                "photo_url": session.existing_product.photo_url,
                "description": session.existing_product.description,
                "tags": session.existing_product.tags,
                "active": session.existing_product.active,
            }

        # Serialize photo_quality if present
        if session.photo_quality:
            data["photo_quality"] = {
                "status": session.photo_quality.status.value,
                "width": session.photo_quality.width,
                "height": session.photo_quality.height,
                "sharpness": session.photo_quality.sharpness,
                "brightness_low": session.photo_quality.brightness_low,
                "brightness_high": session.photo_quality.brightness_high,
                "warnings": session.photo_quality.warnings,
            }

        return json.dumps(data, ensure_ascii=False)

    def _deserialize_session(self, json_str: str) -> IntakeSession:
        """Deserialize JSON string to IntakeSession."""
        from app.models import IntakeSession, PhotoQualityResult, PhotoStatus, Product

        data = json.loads(json_str)

        # Reconstruct existing_product
        existing_product = None
        if data.get("existing_product"):
            ep = data["existing_product"]
            existing_product = Product(
                row_number=ep["row_number"],
                sku=ep["sku"],
                name=ep["name"],
                price=ep["price"],
                stock=ep["stock"],
                photo_url=ep.get("photo_url", ""),
                description=ep.get("description", ""),
                tags=ep.get("tags", ""),
                active=ep.get("active", True),
            )

        # Reconstruct photo_quality
        photo_quality = None
        if data.get("photo_quality"):
            pq = data["photo_quality"]
            photo_quality = PhotoQualityResult(
                status=PhotoStatus(pq["status"]),
                width=pq["width"],
                height=pq["height"],
                sharpness=pq["sharpness"],
                brightness_low=pq["brightness_low"],
                brightness_high=pq["brightness_high"],
                warnings=pq.get("warnings", []),
            )

        # Parse created_at
        created_at = datetime.now()
        if data.get("created_at"):
            with contextlib.suppress(ValueError):
                created_at = datetime.fromisoformat(data["created_at"])

        return IntakeSession(
            user_id=data["user_id"],
            name=data.get("name"),
            price=data.get("price"),
            quantity=data.get("quantity"),
            sku=data.get("sku"),
            existing_product=existing_product,
            is_new_product=data.get("is_new_product", True),
            photo_file_id=data.get("photo_file_id"),
            drive_file_id=data.get("drive_file_id"),
            drive_url=data.get("drive_url"),
            photo_quality=photo_quality,
            fingerprint=data.get("fingerprint"),
            created_at=created_at,
        )

    async def get(self, user_id: int) -> IntakeSession | None:
        """Get active session for user."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT session_data, updated_at FROM intake_sessions WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Check TTL
            updated_at = datetime.fromisoformat(row["updated_at"])
            if datetime.now() - updated_at > timedelta(hours=SESSION_TTL_HOURS):
                await self.delete(user_id)
                logger.info(
                    "intake_session_expired",
                    extra={"user_id": user_id, "updated_at": updated_at.isoformat()},
                )
                return None

            try:
                return self._deserialize_session(row["session_data"])
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(
                    "intake_session_corrupted",
                    extra={"user_id": user_id, "error": str(e)},
                )
                await self.delete(user_id)
                return None

    async def save(self, session: IntakeSession) -> None:
        """Save or update session."""
        await self._ensure_initialized()

        now = datetime.now().isoformat()
        session_data = self._serialize_session(session)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO intake_sessions (user_id, session_data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    session_data = excluded.session_data,
                    updated_at = excluded.updated_at
                """,
                (session.user_id, session_data, now, now),
            )
            await db.commit()

        logger.debug(
            "intake_session_saved",
            extra={"user_id": session.user_id},
        )

    async def delete(self, user_id: int) -> bool:
        """Delete user's session."""
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM intake_sessions WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(
                "intake_session_deleted",
                extra={"user_id": user_id},
            )

        return deleted

    async def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of deleted rows."""
        await self._ensure_initialized()

        cutoff = (datetime.now() - timedelta(hours=SESSION_TTL_HOURS)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM intake_sessions WHERE updated_at < ?",
                (cutoff,),
            )
            await db.commit()
            count = cursor.rowcount

        if count > 0:
            logger.info(
                "intake_sessions_cleanup",
                extra={"deleted_count": count},
            )

        return count


# Global instance
intake_session_store = IntakeSessionStore()
