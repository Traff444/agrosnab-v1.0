"""Main menu button handlers.

Note: /start command is handled in critical.py with highest priority.
This module only handles the reply keyboard button "❌ Отмена".
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import main_menu_keyboard
from app.services.intake_service import intake_service

router = Router()


@router.message(F.text == "❌ Отмена")
async def handle_cancel(message: Message, state: FSMContext) -> None:
    """Handle cancel from reply keyboard."""
    await state.clear()

    if message.from_user:
        await intake_service.clear_session(message.from_user.id)

    await message.answer(
        "🏠 Действие отменено. Возврат в главное меню.",
        reply_markup=main_menu_keyboard(),
    )
