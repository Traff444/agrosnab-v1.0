"""Navigation handlers for catalog pagination info."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data.startswith("pageinfo:"))
async def pageinfo_handler(callback: CallbackQuery):
    """Handle page info button click - show toast with current page."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Ошибка")
        return
    page = parts[1]
    total = parts[2]
    await callback.answer(f"Страница {page} из {total}")
