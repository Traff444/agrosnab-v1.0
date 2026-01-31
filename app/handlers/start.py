"""Start and menu handlers."""

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from .. import cart_store
from ..keyboards import back_to_menu_kb, main_menu_kb, persistent_menu
from ..services import ProductService
from ..sheets import SheetsClient

logger = logging.getLogger(__name__)


def register_start_handlers(
    dp: Dispatcher,
    product_service: ProductService,
    sheets_client: SheetsClient,
) -> None:
    """Register start and menu handlers."""

    @dp.message(CommandStart())
    async def start(m: Message):
        user_id = m.from_user.id
        username = m.from_user.username or m.from_user.first_name or ''

        # AI mode enabled by default
        await cart_store.set_ai_mode(user_id, True)

        # CRM: Log start event
        await cart_store.log_crm_event(user_id, 'start', {
            'username': username,
            'first_name': m.from_user.first_name,
            'source': 'direct',
        })

        # CRM: Upsert lead with consent (user agrees by proceeding)
        try:
            await sheets_client.upsert_lead(
                user_id,
                stage='new',
                username=username,
                consent_at=datetime.now(),
            )
        except Exception as e:
            logger.warning("lead_upsert_failed", extra={"user_id": user_id, "error": str(e)})

        # Show persistent menu at bottom with consent text
        await m.answer(
            "👋 Добро пожаловать в наш магазин!\n\n"
            "🤖 AI-менеджер уже активен — просто напишите что вам нужно!\n"
            "Например: «что есть?» или «добавь 5 золотой»\n\n"
            "📋 Нажимая кнопки ниже, вы соглашаетесь с обработкой данных.\n\n"
            "Используйте кнопки снизу:",
            reply_markup=persistent_menu(),
        )
        # Show inline menu with additional options
        await m.answer(
            "👇 Дополнительные действия:",
            reply_markup=main_menu_kb(),
        )

    @dp.message(F.text == "📋 Меню")
    async def text_menu(m: Message):
        await m.answer(
            "📋 <b>Главное меню</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )

    @dp.callback_query(F.data == "menu")
    async def menu(cb: CallbackQuery):
        try:
            await cb.message.edit_text(
                "📋 <b>Меню</b>\n\nВыберите действие:",
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            await cb.message.answer(
                "📋 <b>Меню</b>\n\nВыберите действие:",
                parse_mode="HTML",
                reply_markup=main_menu_kb(),
            )
        await cb.answer()

    @dp.callback_query(F.data == "info:terms")
    async def terms(cb: CallbackQuery):
        from ..utils import escape_html

        settings = product_service.get_settings()
        min_sum = settings.get("Мин. сумма заказа", 5000)
        t1 = escape_html(settings.get("Условие 1", ""))
        text = f"📌 <b>Условия</b>\n\nМинимальная сумма заказа: {min_sum} ₽\n{t1}"
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "noop")
    async def noop(cb: CallbackQuery):
        await cb.answer()
