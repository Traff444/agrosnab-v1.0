"""Application configuration using Pydantic Settings."""

import base64
import json
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str
    owner_telegram_ids: list[int] = []

    # Google Sheets
    google_sheets_id: str
    google_service_account_json_path: str = ""
    google_service_account_json_b64: str = ""

    # Google Drive (deprecated, using Cloudinary instead)
    drive_folder_id: str = ""

    # Cloudinary (photo storage)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Photo quality thresholds
    photo_min_size: int = 800  # Минимальная ширина/высота в пикселях
    photo_sharpness_threshold: float = 100.0  # Laplacian variance threshold
    photo_brightness_min: int = 40  # Шкала 0-255 (избежать слишком тёмных)
    photo_brightness_max: int = 220  # Шкала 0-255 (избежать пересвета)

    # OpenAI (for AI summaries)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Application
    log_level: str = "INFO"
    timezone: str = "Europe/Vilnius"

    # Monitoring (Sentry)
    sentry_dsn: str = ""
    environment: str = "production"

    # Paths
    tmp_dir: Path = Path("tmp")
    db_path: Path = Path("data/confirm_actions.db")

    @field_validator("owner_telegram_ids", mode="before")
    @classmethod
    def parse_owner_ids(cls, v: str | list[int] | int) -> list[int]:
        """Parse comma-separated string of IDs into list of integers."""
        if isinstance(v, list):
            return v
        if isinstance(v, int):
            return [v]
        if isinstance(v, str) and v.strip():
            return [int(id_.strip()) for id_ in v.split(",") if id_.strip()]
        return []

    @model_validator(mode="after")
    def validate_google_credentials(self) -> "Settings":
        """Ensure at least one Google credential method is provided."""
        if not self.google_service_account_json_path and not self.google_service_account_json_b64:
            raise ValueError(
                "Either GOOGLE_SERVICE_ACCOUNT_JSON_PATH or "
                "GOOGLE_SERVICE_ACCOUNT_JSON_B64 must be provided"
            )
        return self

    @model_validator(mode="after")
    def validate_cloudinary_credentials(self) -> "Settings":
        """Ensure all Cloudinary credentials are provided together or none."""
        cloudinary_fields = [
            self.cloudinary_cloud_name,
            self.cloudinary_api_key,
            self.cloudinary_api_secret,
        ]
        filled = [bool(f) for f in cloudinary_fields]

        if any(filled) and not all(filled):
            missing = []
            if not self.cloudinary_cloud_name:
                missing.append("CLOUDINARY_CLOUD_NAME")
            if not self.cloudinary_api_key:
                missing.append("CLOUDINARY_API_KEY")
            if not self.cloudinary_api_secret:
                missing.append("CLOUDINARY_API_SECRET")
            raise ValueError(
                f"Cloudinary partially configured. Missing: {', '.join(missing)}. "
                "Provide all Cloudinary credentials or none."
            )
        return self

    @property
    def cloudinary_enabled(self) -> bool:
        """Check if Cloudinary is fully configured."""
        return bool(
            self.cloudinary_cloud_name
            and self.cloudinary_api_key
            and self.cloudinary_api_secret
        )

    def get_google_credentials_info(self) -> dict:
        """Get Google service account credentials as dictionary."""
        if self.google_service_account_json_b64:
            decoded = base64.b64decode(self.google_service_account_json_b64)
            return json.loads(decoded)

        if self.google_service_account_json_path:
            path = Path(self.google_service_account_json_path)
            if not path.exists():
                raise FileNotFoundError(f"Service account file not found: {path}")
            return json.loads(path.read_text())

        raise ValueError("No Google credentials configured")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
