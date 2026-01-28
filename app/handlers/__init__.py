"""Handlers package for the Telegram bot."""

from .ai import register_ai_handlers
from .cart import register_cart_handlers
from .catalog import register_catalog_handlers
from .start import register_start_handlers

__all__ = [
    "register_start_handlers",
    "register_catalog_handlers",
    "register_cart_handlers",
    "register_ai_handlers",
]
