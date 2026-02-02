"""CRM handlers for Owner Bot."""

import logging
from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.crm_db import (
    format_messages_for_display,
    generate_ai_summary,
    get_user_messages_count,
)
from app.keyboards import main_menu_keyboard
from app.sheets import sheets_client

logger = logging.getLogger(__name__)

router = Router()


async def _safe_edit_text(
    cb: CallbackQuery,
    text: str,
    reply_markup: Any = None,
    **kwargs: Any,
) -> bool:
    """Safely edit message text, fallback to answer on failure."""
    try:
        await cb.message.edit_text(text, reply_markup=reply_markup, **kwargs)
        return True
    except TelegramBadRequest as e:
        logger.debug("Cannot edit CRM message: %s", e)
        await cb.message.answer(text, reply_markup=reply_markup, **kwargs)
        return False


async def _safe_edit_reply_markup(
    cb: CallbackQuery,
    reply_markup: Any = None,
) -> bool:
    """Safely edit reply markup."""
    try:
        await cb.message.edit_reply_markup(reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        logger.debug("Cannot edit CRM reply markup: %s", e)
        return False


# Stage emoji mapping
STAGE_EMOJI = {
    "new": "🆕",
    "engaged": "👀",
    "cart": "🛒",
    "checkout": "📝",
    "customer": "✅",
    "repeat": "🌟",
}

# Tag options for leads
TAG_OPTIONS = ["vip", "problem", "discount", "cdek", "pickup", "wholesale"]


class CRMState(StatesGroup):
    """FSM states for CRM operations."""

    searching = State()
    adding_note = State()
    editing_tags = State()


def crm_menu_keyboard() -> InlineKeyboardMarkup:
    """CRM main menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📈 Воронка", callback_data="crm:funnel")],
            [InlineKeyboardButton(text="👥 Последние лиды", callback_data="crm:leads")],
            [InlineKeyboardButton(text="🔍 Поиск клиента", callback_data="crm:search")],
            [InlineKeyboardButton(text="📋 Отчёт за день", callback_data="crm:report")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="crm:back")],
        ]
    )


def lead_card_keyboard(
    user_id: int, has_prev: bool = False, has_next: bool = False
) -> InlineKeyboardMarkup:
    """Keyboard for lead card."""
    builder = InlineKeyboardBuilder()

    # Action buttons
    builder.button(text="📝 Заметка", callback_data=f"crm:note:{user_id}")
    builder.button(text="🏷 Теги", callback_data=f"crm:tags:{user_id}")
    builder.button(text="📜 История", callback_data=f"crm:history:{user_id}")

    # Navigation
    nav_row = []
    if has_prev:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Пред.", callback_data=f"crm:lead_prev:{user_id}")
        )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(text="След. ▶️", callback_data=f"crm:lead_next:{user_id}")
        )

    builder.adjust(3)  # 3 buttons per row

    kb = builder.as_markup()
    if nav_row:
        kb.inline_keyboard.append(nav_row)
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 К списку", callback_data="crm:leads")])

    return kb


def tags_keyboard(user_id: int, current_tags: list[str]) -> InlineKeyboardMarkup:
    """Keyboard for editing tags."""
    builder = InlineKeyboardBuilder()

    for tag in TAG_OPTIONS:
        emoji = "✅" if tag in current_tags else "⬜"
        builder.button(text=f"{emoji} {tag}", callback_data=f"crm:tag_toggle:{user_id}:{tag}")

    builder.adjust(2)

    kb = builder.as_markup()
    kb.inline_keyboard.append(
        [InlineKeyboardButton(text="💾 Готово", callback_data=f"crm:lead:{user_id}")]
    )

    return kb


def format_lead_card(lead: dict) -> str:
    """Format lead data as a Telegram message."""
    stage = lead.get("stage", "new")
    stage_emoji = STAGE_EMOJI.get(stage, "❓")

    user_id = lead.get("user_id", "?")
    username = lead.get("username", "")
    first_seen = lead.get("first_seen_at", "")[:10] if lead.get("first_seen_at") else "—"
    last_seen = lead.get("last_seen_at", "")[:16] if lead.get("last_seen_at") else "—"

    orders_count = int(lead.get("orders_count") or 0)
    lifetime_value = int(lead.get("lifetime_value") or 0)
    last_order = lead.get("last_order_id", "") or "—"

    phone = lead.get("phone", "")
    phone_masked = phone[:4] + "***" + phone[-2:] if phone and len(phone) > 6 else phone or "—"

    tags = lead.get("tags", "") or "—"
    notes = lead.get("notes", "") or "—"

    return (
        f"👤 *Клиент #{user_id}*\n"
        f"├ Имя: {username or '—'}\n"
        f"├ Стадия: {stage_emoji} {stage}\n"
        f"├ Заказов: {orders_count} ({lifetime_value:,} ₽)\n"
        f"├ Последний: {last_order}\n"
        f"├ Первый визит: {first_seen}\n"
        f"├ Последний: {last_seen}\n"
        f"├ Телефон: {phone_masked}\n"
        f"├ Теги: {tags}\n"
        f"└ Заметки: {notes}"
    )


def format_funnel(stats: dict) -> str:
    """Format funnel statistics."""
    total = stats.get("total", 0)
    if total == 0:
        return "📊 *Воронка пуста*\n\nНет данных о лидах."

    new = stats.get("new", 0)
    engaged = stats.get("engaged", 0)
    cart = stats.get("cart", 0)
    checkout = stats.get("checkout", 0)
    customer = stats.get("customer", 0)
    repeat = stats.get("repeat", 0)

    # Calculate percentages
    def pct(n):
        return f"{n / total * 100:.0f}%" if total > 0 else "0%"

    # Conversion rates
    engaged_rate = f"{engaged / new * 100:.0f}%" if new > 0 else "—"
    cart_rate = f"{cart / engaged * 100:.0f}%" if engaged > 0 else "—"
    checkout_rate = f"{checkout / cart * 100:.0f}%" if cart > 0 else "—"
    customer_rate = f"{customer / checkout * 100:.0f}%" if checkout > 0 else "—"

    return (
        f"📊 *Воронка продаж*\n\n"
        f"🆕 Новые: {new} ({pct(new)})\n"
        f"    ↓ {engaged_rate}\n"
        f"👀 Смотрели: {engaged} ({pct(engaged)})\n"
        f"    ↓ {cart_rate}\n"
        f"🛒 Корзина: {cart} ({pct(cart)})\n"
        f"    ↓ {checkout_rate}\n"
        f"📝 Оформляют: {checkout} ({pct(checkout)})\n"
        f"    ↓ {customer_rate}\n"
        f"✅ Покупатели: {customer} ({pct(customer)})\n"
        f"🌟 Повторные: {repeat} ({pct(repeat)})\n\n"
        f"📈 Всего лидов: {total}"
    )


# =============================================================================
# Handlers
# =============================================================================


@router.message(F.text == "📊 CRM")
async def cmd_crm(message: Message, state: FSMContext) -> None:
    """CRM main menu."""
    await state.clear()  # Clear FSM state to avoid conflicts with intake flow
    await message.answer(
        "📊 *CRM — Управление клиентами*\n\nВыберите действие:",
        reply_markup=crm_menu_keyboard(),
    )


@router.callback_query(F.data == "crm:back")
async def crm_back(cb: CallbackQuery, state: FSMContext) -> None:
    """Return to main menu."""
    await state.clear()
    await _safe_edit_text(cb, "🏠 Возврат в главное меню")
    await cb.message.answer(
        "Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "crm:funnel")
async def crm_funnel(cb: CallbackQuery) -> None:
    """Show funnel statistics."""
    await cb.answer("Загрузка...")

    try:
        stats = await sheets_client.get_funnel_stats()
        text = format_funnel(stats)
    except Exception as e:
        logger.error("funnel_stats_failed", extra={"error": str(e)})
        text = "❌ Не удалось загрузить статистику воронки"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="crm:funnel")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="crm:menu")],
        ]
    )

    await _safe_edit_text(cb, text, reply_markup=kb)


@router.callback_query(F.data == "crm:menu")
async def crm_menu(cb: CallbackQuery) -> None:
    """Return to CRM menu."""
    await _safe_edit_text(
        cb,
        "📊 *CRM — Управление клиентами*\n\nВыберите действие:",
        reply_markup=crm_menu_keyboard(),
    )
    await cb.answer()


@router.callback_query(F.data == "crm:leads")
async def crm_leads(cb: CallbackQuery) -> None:
    """Show recent leads list."""
    await cb.answer("Загрузка...")

    try:
        leads = await sheets_client.get_leads(limit=10)
    except Exception as e:
        logger.error("leads_fetch_failed", extra={"error": str(e)})
        leads = []

    if not leads:
        await _safe_edit_text(
            cb,
            "👥 *Последние лиды*\n\nСписок пуст. Пока нет данных о клиентах.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="crm:menu")]]
            ),
        )
        return

    text = "👥 *Последние лиды*\n\n"
    builder = InlineKeyboardBuilder()

    for lead in leads[:10]:
        user_id = lead.get("user_id", "?")
        username = lead.get("username", "")[:15] or f"#{user_id}"
        stage = lead.get("stage", "new")
        stage_emoji = STAGE_EMOJI.get(stage, "❓")
        orders = int(lead.get("orders_count") or 0)

        label = f"{stage_emoji} {username}"
        if orders > 0:
            label += f" ({orders} заказ{'ов' if orders > 1 else ''})"

        builder.button(text=label, callback_data=f"crm:lead:{user_id}")

    builder.adjust(1)
    builder.button(text="🔙 Назад", callback_data="crm:menu")

    await _safe_edit_text(cb, text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("crm:lead:"))
async def crm_lead_detail(cb: CallbackQuery) -> None:
    """Show lead detail card."""
    try:
        user_id = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Ошибка: неверный ID", show_alert=True)
        return

    await cb.answer("Загрузка...")

    lead = await sheets_client.get_lead_by_user_id(user_id)
    if not lead:
        await _safe_edit_text(
            cb,
            f"❌ Клиент #{user_id} не найден",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 К списку", callback_data="crm:leads")]
                ]
            ),
        )
        return

    text = format_lead_card(lead)
    kb = lead_card_keyboard(user_id)

    await _safe_edit_text(cb, text, reply_markup=kb)


@router.callback_query(F.data.startswith("crm:history:"))
async def crm_message_history(cb: CallbackQuery) -> None:
    """Show message history for a lead."""
    try:
        user_id = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Ошибка: неверный ID", show_alert=True)
        return

    await cb.answer("Загрузка истории...")

    # Get message count
    msg_count = await get_user_messages_count(user_id)

    if msg_count == 0:
        await _safe_edit_text(
            cb,
            f"📜 *История сообщений #{user_id}*\n\n"
            "Нет сохранённых сообщений.\n\n"
            "_Сообщения сохраняются только при наличии согласия клиента._",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👤 К карточке", callback_data=f"crm:lead:{user_id}"
                        )
                    ],
                    [InlineKeyboardButton(text="🔙 CRM меню", callback_data="crm:menu")],
                ]
            ),
        )
        return

    # Get formatted messages
    history_text = await format_messages_for_display(user_id, limit=15)

    text = f"📜 *История сообщений #{user_id}*\n_Всего сообщений: {msg_count}_\n\n{history_text}"

    # Truncate if too long
    if len(text) > 4000:
        text = text[:3950] + "\n\n_...обрезано..._"

    # Check if AI summary is available
    settings = get_settings()
    has_ai = bool(settings.openai_api_key)

    keyboard_rows = [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"crm:history:{user_id}")],
    ]

    if has_ai:
        keyboard_rows.append(
            [InlineKeyboardButton(text="🧠 AI-сводка", callback_data=f"crm:summary:{user_id}")]
        )

    keyboard_rows.extend(
        [
            [InlineKeyboardButton(text="👤 К карточке", callback_data=f"crm:lead:{user_id}")],
            [InlineKeyboardButton(text="🔙 CRM меню", callback_data="crm:menu")],
        ]
    )

    await _safe_edit_text(
        cb,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


@router.callback_query(F.data.startswith("crm:summary:"))
async def crm_ai_summary(cb: CallbackQuery) -> None:
    """Generate AI summary of conversation."""
    try:
        user_id = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Ошибка: неверный ID", show_alert=True)
        return

    settings = get_settings()
    if not settings.openai_api_key:
        await cb.answer("AI не настроен (нет OPENAI_API_KEY)", show_alert=True)
        return

    await cb.answer("Генерация AI-сводки...")

    # Generate summary
    summary = await generate_ai_summary(
        user_id=user_id,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    text = f"🧠 *AI-сводка клиента #{user_id}*\n\n{summary}"

    await _safe_edit_text(
        cb,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"crm:summary:{user_id}")],
                [InlineKeyboardButton(text="📜 История", callback_data=f"crm:history:{user_id}")],
                [InlineKeyboardButton(text="👤 К карточке", callback_data=f"crm:lead:{user_id}")],
                [InlineKeyboardButton(text="🔙 CRM меню", callback_data="crm:menu")],
            ]
        ),
    )


@router.callback_query(F.data == "crm:search")
async def crm_search_start(cb: CallbackQuery, state: FSMContext) -> None:
    """Start lead search."""
    await state.set_state(CRMState.searching)
    await _safe_edit_text(
        cb,
        "🔍 *Поиск клиента*\n\nВведите user\\_id, телефон или имя:",
    )
    await cb.answer()


@router.message(CRMState.searching, F.text, ~F.text.startswith("/"))
async def crm_search_query(message: Message, state: FSMContext) -> None:
    """Process search query."""
    query = (message.text or "").strip()
    await state.clear()

    if not query:
        await message.answer(
            "❌ Пустой запрос. Попробуйте ещё раз.",
            reply_markup=crm_menu_keyboard(),
        )
        return

    try:
        results = await sheets_client.search_leads(query)
    except Exception as e:
        logger.error("search_failed", extra={"error": str(e)})
        results = []

    if not results:
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.",
            reply_markup=crm_menu_keyboard(),
        )
        return

    if len(results) == 1:
        # Show single result directly
        lead = results[0]
        user_id = lead.get("user_id")
        text = format_lead_card(lead)
        kb = lead_card_keyboard(int(user_id) if user_id else 0)
        await message.answer(text, reply_markup=kb)
    else:
        # Show list
        text = f"🔍 Найдено {len(results)} результатов:\n\n"
        builder = InlineKeyboardBuilder()

        for lead in results[:10]:
            user_id = lead.get("user_id", "?")
            username = lead.get("username", "")[:15] or f"#{user_id}"
            stage = lead.get("stage", "new")
            stage_emoji = STAGE_EMOJI.get(stage, "❓")

            builder.button(text=f"{stage_emoji} {username}", callback_data=f"crm:lead:{user_id}")

        builder.adjust(1)
        builder.button(text="🔙 CRM меню", callback_data="crm:menu")

        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("crm:note:"))
async def crm_add_note_start(cb: CallbackQuery, state: FSMContext) -> None:
    """Start adding note to lead."""
    try:
        user_id = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Ошибка", show_alert=True)
        return

    await state.set_state(CRMState.adding_note)
    await state.update_data(target_user_id=user_id)

    await cb.message.answer(f"📝 *Заметка для клиента #{user_id}*\n\nВведите текст заметки:")
    await cb.answer()


@router.message(CRMState.adding_note, F.text, ~F.text.startswith("/"))
async def crm_add_note_save(message: Message, state: FSMContext) -> None:
    """Save note to lead."""
    data = await state.get_data()
    user_id = data.get("target_user_id")
    await state.clear()

    if not user_id:
        await message.answer("❌ Ошибка: клиент не найден")
        return

    note_text = (message.text or "").strip()
    if not note_text:
        await message.answer("❌ Заметка пуста")
        return

    # Append timestamp
    timestamp = datetime.now().strftime("%d.%m %H:%M")
    note_with_ts = f"[{timestamp}] {note_text}"

    try:
        # Get existing notes and append
        lead = await sheets_client.get_lead_by_user_id(user_id)
        existing_notes = lead.get("notes", "") if lead else ""
        if existing_notes and existing_notes != "—":
            new_notes = f"{existing_notes}; {note_with_ts}"
        else:
            new_notes = note_with_ts

        await sheets_client.update_lead_notes(user_id, new_notes)
        await message.answer(
            f"✅ Заметка сохранена для клиента #{user_id}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👤 К карточке", callback_data=f"crm:lead:{user_id}"
                        )
                    ],
                    [InlineKeyboardButton(text="🔙 CRM меню", callback_data="crm:menu")],
                ]
            ),
        )
    except Exception as e:
        logger.error("note_save_failed", extra={"error": str(e)})
        await message.answer("❌ Не удалось сохранить заметку")


@router.callback_query(F.data.startswith("crm:tags:"))
async def crm_edit_tags(cb: CallbackQuery) -> None:
    """Show tags editor."""
    try:
        user_id = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Ошибка", show_alert=True)
        return

    lead = await sheets_client.get_lead_by_user_id(user_id)
    current_tags_str = lead.get("tags", "") if lead else ""
    current_tags = [t.strip() for t in current_tags_str.split(",") if t.strip()]

    await _safe_edit_text(
        cb,
        f"🏷 *Теги для клиента #{user_id}*\n\nНажмите на тег чтобы добавить/убрать:",
        reply_markup=tags_keyboard(user_id, current_tags),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("crm:tag_toggle:"))
async def crm_toggle_tag(cb: CallbackQuery) -> None:
    """Toggle a tag on/off."""
    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("Ошибка", show_alert=True)
        return

    try:
        user_id = int(parts[2])
        tag = parts[3]
    except (ValueError, IndexError):
        await cb.answer("Ошибка", show_alert=True)
        return

    lead = await sheets_client.get_lead_by_user_id(user_id)
    current_tags_str = lead.get("tags", "") if lead else ""
    current_tags = [t.strip() for t in current_tags_str.split(",") if t.strip()]

    # Toggle tag
    if tag in current_tags:
        current_tags.remove(tag)
    else:
        current_tags.append(tag)

    # Save
    new_tags_str = ", ".join(current_tags)
    try:
        await sheets_client.update_lead_tags(user_id, new_tags_str)
    except Exception as e:
        logger.error("tags_update_failed", extra={"error": str(e)})
        await cb.answer("Ошибка сохранения", show_alert=True)
        return

    # Update keyboard
    await _safe_edit_reply_markup(cb, reply_markup=tags_keyboard(user_id, current_tags))
    await cb.answer(f"{'➕' if tag in current_tags else '➖'} {tag}")


@router.callback_query(F.data == "crm:report")
async def crm_daily_report(cb: CallbackQuery) -> None:
    """Show daily report."""
    await cb.answer("Загрузка...")

    try:
        stats = await sheets_client.get_funnel_stats()
        orders = await sheets_client.get_orders_summary()
    except Exception as e:
        logger.error("report_fetch_failed", extra={"error": str(e)})
        await _safe_edit_text(
            cb,
            "❌ Не удалось загрузить отчёт",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="crm:menu")]]
            ),
        )
        return

    today = datetime.now().strftime("%d.%m.%Y")
    orders_count = orders.get("orders_count", 0)
    orders_total = orders.get("orders_total", 0)
    avg_check = orders_total // orders_count if orders_count > 0 else 0

    total_leads = stats.get("total", 0)
    customers = stats.get("customer", 0) + stats.get("repeat", 0)
    conversion = f"{customers / total_leads * 100:.1f}%" if total_leads > 0 else "—"

    text = (
        f"📋 *Отчёт за {today}*\n\n"
        f"*Заказы:*\n"
        f"├ Количество: {orders_count}\n"
        f"├ Сумма: {orders_total:,} ₽\n"
        f"└ Средний чек: {avg_check:,} ₽\n\n"
        f"*Воронка:*\n"
        f"├ Всего лидов: {total_leads}\n"
        f"├ Покупателей: {customers}\n"
        f"└ Конверсия: {conversion}\n\n"
        f"*По стадиям:*\n"
        f"🆕 {stats.get('new', 0)} → 👀 {stats.get('engaged', 0)} → "
        f"🛒 {stats.get('cart', 0)} → 📝 {stats.get('checkout', 0)} → "
        f"✅ {stats.get('customer', 0)} → 🌟 {stats.get('repeat', 0)}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="crm:report")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="crm:menu")],
        ]
    )

    await _safe_edit_text(cb, text, reply_markup=kb)
