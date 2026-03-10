"""Start and menu handlers."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import cart_store
from ..analytics import track, identify, alias
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
        username = m.from_user.username or m.from_user.first_name or ""

        # AI mode disabled by default (user can enable via menu)
        await cart_store.set_ai_mode(user_id, False)

        # CRM: Log start event
        await cart_store.log_crm_event(
            user_id,
            "start",
            {
                "username": username,
                "first_name": m.from_user.first_name,
                "source": "direct",
            },
        )

        # PostHog: identify user and track start
        args = m.get_args() or ""
        ph_match = re.search(r"ph_(.+)$", args)

        identify(user_id, {
            "username": m.from_user.username or "",
            "first_name": m.from_user.first_name or "",
        })
        track(user_id, "bot_start", {"source": "deeplink" if args else "organic", "deeplink": args})

        if ph_match:
            alias(user_id, ph_match.group(1))

        # CRM: Upsert lead with consent (user agrees by proceeding)
        try:
            await sheets_client.upsert_lead(
                user_id,
                stage="new",
                username=username,
                consent_at=datetime.now(),
            )
        except Exception as e:
            logger.warning("lead_upsert_failed", extra={"user_id": user_id, "error": str(e)})

        # Get cart count for display
        cart_count = await cart_store.get_cart_count(user_id)

        # Set persistent keyboard (reply buttons at bottom)
        await m.answer(
            "👋 <b>Добро пожаловать в наш магазин!</b>\n\n"
            "📦 Выберите действие ниже.\n"
            "🤖 AI-менеджер доступен в меню.\n\n"
            "📋 Нажимая кнопки, вы соглашаетесь с обработкой данных.",
            parse_mode="HTML",
            reply_markup=persistent_menu(),
        )
        # Show inline menu
        await m.answer(
            "📋 <b>Главное меню:</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(cart_count),
        )

    @dp.message(F.text.endswith("Меню"))
    async def text_menu(m: Message):
        cart_count = await cart_store.get_cart_count(m.from_user.id)
        await m.answer(
            "📋 <b>Главное меню</b>\n\nВыберите действие:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(cart_count),
        )

    @dp.callback_query(F.data == "menu")
    async def menu(cb: CallbackQuery):
        cart_count = await cart_store.get_cart_count(cb.from_user.id)
        try:
            await cb.message.edit_text(
                "📋 <b>Меню</b>\n\nВыберите действие:",
                parse_mode="HTML",
                reply_markup=main_menu_kb(cart_count),
            )
        except Exception:
            await cb.message.answer(
                "📋 <b>Меню</b>\n\nВыберите действие:",
                parse_mode="HTML",
                reply_markup=main_menu_kb(cart_count),
            )
        await cb.answer()

    @dp.callback_query(F.data == "info:terms")
    async def terms(cb: CallbackQuery):
        settings = product_service.get_settings()
        min_sum = settings.get("Мин. сумма заказа", 1000)
        discount_threshold = settings.get("Розница. скидка. порог", 100)
        discount_percent = settings.get("Розница. скидка. процент", 10)
        wholesale_min = settings.get("Опт. мин. сумма", 20000)

        text = (
            "📌 <b>Условия</b>\n\n"
            "🛒 <b>Розница:</b>\n"
            f"• Минимальный заказ: {min_sum} ₽\n"
            f"• Скидка {discount_percent}% при покупке от {discount_threshold} шт.\n"
            "• Оплата при получении\n\n"
            "📦 <b>Опт:</b>\n"
            f"• Заказ от {wholesale_min:,} ₽\n"
            "• Менеджер выставит счёт\n"
            "• Индивидуальные условия"
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "info:delivery")
    async def info_delivery(cb: CallbackQuery):
        text = (
            "🚚 <b>Доставка</b>\n\n"
            "📦 <b>ПВЗ СДЭК</b>\n"
            "Доставка в пункт выдачи СДЭК по всей России.\n\n"
            "📮 <b>Почта России</b>\n"
            "Доставка Почтой России (от 1 000 ₽).\n\n"
            "🚗 <b>Курьер</b>\n"
            "Курьерская доставка по Москве/МО, СПб/Ленобласти.\n\n"
            "🏪 <b>Самовывоз</b>\n"
            "Фуд Сити, м. Корниловская\n\n"
            "💡 Стоимость доставки рассчитывает менеджер."
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "info:payment")
    async def info_payment(cb: CallbackQuery):
        text = (
            "💳 <b>Оплата</b>\n\n"
            "🛒 <b>Розница:</b>\n"
            "• Оплата при получении\n"
            "• Наличные или перевод\n\n"
            "📦 <b>Опт (от 20 000 ₽):</b>\n"
            "• Менеджер выставит счёт\n"
            "• Безналичный расчёт\n"
            "• Работа по договору"
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "info:pickup")
    async def info_pickup(cb: CallbackQuery):
        text = (
            "🏪 <b>Самовывоз</b>\n\n"
            "📍 <b>Адрес:</b>\n"
            "Фуд Сити, м. Корниловская\n"
            "Вход 2/3, этаж 2, линия 22, павильон 60\n"
            "«Табачный мир»\n\n"
            "🕐 <b>Режим работы:</b>\n"
            "Пн-Вс: 10:00 — 17:00\n\n"
            "💡 При самовывозе оплата на месте."
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "info:manager")
    async def info_manager(cb: CallbackQuery):
        text = (
            "👨‍💼 <b>Связаться с менеджером</b>\n\n"
            "📱 <b>Telegram:</b> @mahoorka_bot\n"
            "📞 <b>Телефон:</b> +7 (916) 481-07-69\n"
            "📧 <b>Email:</b> info@makhorkamarket.store\n\n"
            "🕐 Время работы: Пн-Вс 10:00 — 17:00"
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "wholesale:request")
    async def wholesale_request(cb: CallbackQuery):
        text = (
            "📋 <b>Запрос оптового прайса</b>\n\n"
            "Для получения оптового прайса и индивидуальных условий "
            "свяжитесь с менеджером удобным способом:\n\n"
            "📱 <b>Telegram</b> — напишите менеджеру напрямую\n"
            "📧 <b>Email:</b> info@makhorkamarket.store\n\n"
            "💡 Укажите интересующие позиции и объём, "
            "менеджер подготовит персональное предложение."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📱 Написать менеджеру",
                        url="https://t.me/+79164810769",
                    ),
                ],
                [
                    InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
                ],
            ]
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await cb.answer()

    @dp.callback_query(F.data == "noop")
    async def noop(cb: CallbackQuery):
        await cb.answer()
