from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Product:
    sku: str
    name: str
    desc_short: str
    desc_full: str
    price_rub: int
    stock: int
    supplier_id: str
    photo_url: str
    active: bool
    tags: str


@dataclass
class OrderDraft:
    user_id: int
    phone: str
    delivery: str
    pickup_point: str
    items: list[tuple[str, int]]  # (sku, qty)
    total_rub: int
    created_at: datetime
    order_id: str
