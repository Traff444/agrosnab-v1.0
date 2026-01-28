"""Data models for the Owner Bot."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IntakeConfidence(str, Enum):
    """Confidence level of intake parser."""

    HIGH = "high"
    LOW = "low"


class PhotoStatus(str, Enum):
    """Photo quality analysis status."""

    OK = "ok"
    WARNING = "warning"


@dataclass
class ParsedIntake:
    """Result of parsing intake quick string."""

    name: str | None = None
    price: float | None = None
    quantity: int | None = None
    confidence: IntakeConfidence = IntakeConfidence.LOW
    raw_input: str = ""


@dataclass
class PhotoQualityResult:
    """Result of photo quality analysis."""

    status: PhotoStatus
    width: int
    height: int
    sharpness: float
    brightness_low: float
    brightness_high: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class PhotoEnhanceResult:
    """Result of photo enhancement."""

    path: str
    original_size: tuple[int, int]
    final_size: tuple[int, int]
    was_cropped: bool = False
    was_denoised: bool = False


@dataclass
class DriveUploadResult:
    """Result of Drive file upload."""

    file_id: str
    public_url: str
    permissions_ok: bool = True
    error_message: str | None = None


@dataclass
class Product:
    """Product data from Google Sheets."""

    row_number: int
    sku: str
    name: str
    price: float
    stock: int
    photo_url: str = ""
    description: str = ""
    tags: str = ""
    active: bool = True
    last_intake_at: datetime | None = None
    last_intake_qty: int | None = None
    last_updated_by: str | None = None

    @classmethod
    def from_row(cls, row_number: int, data: dict[str, Any], col_map: dict[str, int]) -> "Product":
        """Create Product from sheet row data."""

        def get_val(key: str, default: Any = "", aliases: list[str] | None = None) -> Any:
            """Get value by key, trying aliases if not found."""
            if key in data:
                return data.get(key, default)
            if aliases:
                for alias in aliases:
                    if alias in data:
                        return data.get(alias, default)
            return default

        # Parse price, handling currency format like "1 000 ₽" or "1\xa0000 ₽"
        price_raw = get_val("Цена", 0, ["Цена_руб"])
        if isinstance(price_raw, str):
            # Remove spaces (regular and non-breaking), currency symbols
            price_raw = price_raw.replace(" ", "").replace("\xa0", "").replace("₽", "").replace(",", ".")
        price = float(price_raw or 0)

        return cls(
            row_number=row_number,
            sku=str(get_val("SKU", "")),
            name=str(get_val("Наименование", "")),
            price=price,
            stock=int(get_val("Остаток", 0, ["Остаток_расчет"]) or 0),
            photo_url=str(get_val("Фото", "", ["Фото_URL"])),
            description=str(get_val("Описание_кратко", "")),
            tags=str(get_val("Теги", "")),
            active=str(get_val("Активен", "да")).lower() in ("true", "да", "yes", "1"),
            last_intake_at=None,  # Parsed separately if needed
            last_intake_qty=int(get_val("last_intake_qty", 0) or 0) or None,
            last_updated_by=get_val("last_updated_by") or None,
        )


@dataclass
class IntakeSession:
    """Active intake session state."""

    user_id: int
    name: str | None = None
    price: float | None = None
    quantity: int | None = None
    sku: str | None = None
    existing_product: Product | None = None
    is_new_product: bool = True
    photo_file_id: str | None = None
    drive_file_id: str | None = None
    drive_url: str | None = None
    photo_quality: PhotoQualityResult | None = None
    fingerprint: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def compute_fingerprint(self) -> str:
        """Compute idempotency fingerprint for this intake."""
        import hashlib

        parts = [
            str(self.name or ""),
            str(self.price or ""),
            str(self.quantity or ""),
            str(self.sku or ""),
            str(self.photo_file_id or ""),
        ]
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ConfirmAction:
    """Pending confirmation action with TTL."""

    id: str
    action_type: str
    payload: dict[str, Any]
    owner_id: int
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Order:
    """Order data from Google Sheets."""

    row_number: int
    order_id: str
    created_at: datetime
    customer_name: str
    total: float
    status: str
    items: list[dict[str, Any]] = field(default_factory=list)
