from __future__ import annotations

import re

from pydantic_settings import BaseSettings, SettingsConfigDict


def extract_sheet_id(value: str) -> str:
    # accepts full URL or ID
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
    return m.group(1) if m else value.strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str

    google_sheets_id: str
    google_service_account_json_path: str = "/run/secrets/service_account.json"

    # Optional AI manager
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    auto_write_spisanie: bool = True

    # CDEK delivery integration (optional)
    cdek_client_id: str | None = None
    cdek_client_secret: str | None = None
    cdek_test_mode: bool = True  # Use test API by default
    cdek_demo_mode: bool = False  # Demo mode without real CDEK API (fallback when creds are not set)

    def sheet_id(self) -> str:
        return extract_sheet_id(self.google_sheets_id)

    def cdek_enabled(self) -> bool:
        return bool(self.cdek_client_id and self.cdek_client_secret)
