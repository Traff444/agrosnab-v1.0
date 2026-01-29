"""Google Drive client for photo storage."""

import logging
from pathlib import Path
from typing import BinaryIO

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

from app.config import get_settings
from app.models import DriveUploadResult

logger = logging.getLogger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/drive",  # Full access needed for upload + read existing folders
]


class DriveClient:
    """Google Drive client for photo management."""

    def __init__(self):
        self._service = None

    def _get_credentials(self) -> Credentials:
        """Get Google credentials from settings."""
        settings = get_settings()
        info = settings.get_google_credentials_info()
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    @property
    def service(self):
        """Lazy-loaded Drive service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _make_public_url(self, file_id: str) -> str:
        """Create public URL for Drive file."""
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    async def upload_photo(
        self,
        file_path: str | Path,
        filename: str | None = None,
    ) -> DriveUploadResult:
        """Upload a photo to Drive folder."""
        settings = get_settings()
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if filename is None:
            filename = file_path.name

        file_metadata = {
            "name": filename,
            "parents": [settings.drive_folder_id],
        }

        media = MediaFileUpload(
            str(file_path),
            mimetype="image/jpeg",
            resumable=True,
        )

        file_result = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,webViewLink",
            )
            .execute()
        )

        file_id = file_result["id"]

        # Try to set public permissions
        permissions_ok = True
        error_message = None

        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception as e:
            permissions_ok = False
            error_message = str(e)

        return DriveUploadResult(
            file_id=file_id,
            public_url=self._make_public_url(file_id),
            permissions_ok=permissions_ok,
            error_message=error_message,
        )

    async def upload_photo_bytes(
        self,
        data: BinaryIO,
        filename: str,
    ) -> DriveUploadResult:
        """Upload photo from bytes/file-like object."""
        settings = get_settings()

        file_metadata = {
            "name": filename,
            "parents": [settings.drive_folder_id],
        }

        media = MediaIoBaseUpload(
            data,
            mimetype="image/jpeg",
            resumable=True,
        )

        file_result = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,webViewLink",
            )
            .execute()
        )

        file_id = file_result["id"]

        # Try to set public permissions
        permissions_ok = True
        error_message = None

        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()
        except Exception as e:
            permissions_ok = False
            error_message = str(e)

        return DriveUploadResult(
            file_id=file_id,
            public_url=self._make_public_url(file_id),
            permissions_ok=permissions_ok,
            error_message=error_message,
        )

    async def delete_photo(self, file_id: str) -> bool:
        """Delete a photo from Drive."""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete photo {file_id}: {e}")
            from app.monitoring import capture_exception
            capture_exception(e, {"method": "delete_photo", "file_id": file_id})
            return False

    async def list_folder(self, limit: int = 10) -> list[dict]:
        """List files in the configured folder."""
        settings = get_settings()

        result = (
            self.service.files()
            .list(
                q=f"'{settings.drive_folder_id}' in parents and trashed = false",
                pageSize=limit,
                fields="files(id, name, createdTime, size)",
                orderBy="createdTime desc",
            )
            .execute()
        )

        return result.get("files", [])

    async def test_connection(self) -> dict:
        """Test Drive connection and return diagnostic info."""
        settings = get_settings()

        try:
            # Try to list folder contents
            files = await self.list_folder(limit=1)

            # Try to get folder info
            folder_info = (
                self.service.files()
                .get(fileId=settings.drive_folder_id, fields="id,name")
                .execute()
            )

            return {
                "ok": True,
                "folder_id": settings.drive_folder_id,
                "folder_name": folder_info.get("name", ""),
                "can_list": True,
                "file_count_sample": len(files),
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
            }


# Global client instance
drive_client = DriveClient()
