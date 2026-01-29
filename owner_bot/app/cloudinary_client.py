"""Cloudinary client for photo uploads."""

import logging
from pathlib import Path

import cloudinary
import cloudinary.uploader

from app.config import get_settings
from app.models import DriveUploadResult

logger = logging.getLogger(__name__)


class CloudinaryClient:
    """Client for uploading photos to Cloudinary."""

    def __init__(self):
        settings = get_settings()
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
        self._configured = bool(
            settings.cloudinary_cloud_name
            and settings.cloudinary_api_key
            and settings.cloudinary_api_secret
        )

    async def upload_photo(self, file_path: str, filename: str) -> DriveUploadResult:
        """Upload photo to Cloudinary.

        Args:
            file_path: Local path to the photo file
            filename: Desired filename (used for public_id)

        Returns:
            DriveUploadResult with Cloudinary URL
        """
        if not self._configured:
            return DriveUploadResult(
                file_id="",
                public_url="",
                permissions_ok=False,
                error_message="Cloudinary not configured",
            )

        try:
            public_id = Path(filename).stem

            result = cloudinary.uploader.upload(
                file_path,
                public_id=public_id,
                folder="mahorka_products",
                overwrite=True,
                resource_type="image",
            )

            logger.info(
                "Photo uploaded to Cloudinary: %s -> %s",
                filename,
                result.get("secure_url"),
            )

            return DriveUploadResult(
                file_id=result["public_id"],
                public_url=result["secure_url"],
                permissions_ok=True,
                error_message=None,
            )
        except Exception as e:
            logger.exception("Failed to upload photo to Cloudinary: %s", e)
            return DriveUploadResult(
                file_id="",
                public_url="",
                permissions_ok=False,
                error_message=str(e),
            )

    async def delete_photo(self, public_id: str) -> bool:
        """Delete photo from Cloudinary.

        Args:
            public_id: Cloudinary public ID of the photo

        Returns:
            True if deleted successfully
        """
        if not self._configured:
            return False

        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get("result") == "ok"
        except Exception as e:
            logger.exception("Failed to delete photo from Cloudinary: %s", e)
            return False


cloudinary_client = CloudinaryClient()
