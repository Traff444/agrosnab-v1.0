"""Critical commands that always work regardless of FSM state.

This router must be registered FIRST to ensure these commands
take priority over any FSM state handlers.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import main_menu_keyboard
from app.photo_enhance import cleanup_tmp_files
from app.services.intake_service import intake_service

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start - always clears state and shows main menu."""
    await state.clear()

    user = message.from_user
    name = user.first_name if user else "Владелец"

    if user:
        await intake_service.clear_session(user.id)

    # Lazy cleanup of old tmp files
    deleted = cleanup_tmp_files(max_age_hours=24)

    welcome_text = (
        f"👋 Добро пожаловать, {name}!\n\n"
        "Я помогу вам управлять складом и товарами.\n\n"
        "**Доступные команды:**\n"
        "📦 **Приход товара** — добавить приход\n"
        "📊 **CRM** — воронка, клиенты, отчёты\n"
        "🔍 **Найти товар** — поиск по SKU или названию\n"
        "📋 **Заказы сегодня** — сводка заказов\n"
        "🔧 **Статус** — проверка подключений"
    )

    if deleted > 0:
        welcome_text += f"\n\n🧹 Очищено временных файлов: {deleted}"

    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Handle /cancel - emergency exit from any state."""
    await state.clear()

    if message.from_user:
        await intake_service.clear_session(message.from_user.id)

    await message.answer(
        "🏠 Действие отменено. Возврат в главное меню.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    """Handle /help - show help message."""
    await state.clear()

    if message.from_user:
        await intake_service.clear_session(message.from_user.id)

    await message.answer(
        "📖 **Справка**\n\n"
        "**Команды:**\n"
        "/start — главное меню\n"
        "/cancel — отмена текущего действия\n"
        "/help — эта справка\n\n"
        "**Кнопки меню:**\n"
        "📦 Приход товара — добавить приход\n"
        "📊 CRM — клиенты и воронка\n"
        "🔍 Найти товар — поиск\n"
        "🔧 Статус — проверка системы",
        reply_markup=main_menu_keyboard(),
    )
