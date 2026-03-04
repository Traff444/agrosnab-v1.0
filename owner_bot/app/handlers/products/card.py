"""Product card handlers (intake, photo, edit, more menu)."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards import (
    cancel_keyboard,
    product_actions_keyboard,
    product_more_keyboard,
)
from app.sheets import sheets_client
from app.services.product_service import product_service

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("product_intake_"))
async def handle_product_intake(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quick intake for product."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_intake_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    # Import here to avoid circular imports
    from app.handlers.intake import IntakeState
    from app.services.intake_service import intake_service

    # Create session with product pre-selected
    if callback.from_user:
        session = await intake_service.create_session(callback.from_user.id)
        await intake_service.set_existing_product(session, product)

        await state.set_state(IntakeState.waiting_for_quantity)
        await callback.message.answer(
            f"📦 Приход для **{product.name}**\n"
            f"Текущий остаток: {product.stock} шт.\n\n"
            "📊 Введите количество прихода:",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data.startswith("product_photo_"))
async def handle_product_photo(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle photo update for product."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_photo_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    from app.handlers.intake import IntakeState
    from app.services.intake_service import intake_service

    if callback.from_user:
        session = await intake_service.create_session(callback.from_user.id)
        await intake_service.set_existing_product(session, product)
        session.quantity = 0  # No stock change
        await intake_service.save_session(session)

        await state.set_state(IntakeState.waiting_for_photo)
        await callback.message.answer(
            f"📷 Отправьте новое фото для **{product.name}**:",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data.startswith("product_infinite_"))
async def handle_product_infinite_stock(callback: CallbackQuery) -> None:
    """Toggle infinite stock for product."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_infinite_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    actor = callback.from_user.username or str(callback.from_user.id) if callback.from_user else "unknown"
    updated = await product_service.toggle_infinite_stock(product, updated_by=actor)

    status = "включён ♾" if updated.infinite_stock else "выключен"
    await callback.answer(f"Бесконечный остаток {status}", show_alert=True)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=product_more_keyboard(updated)
        )
    except TelegramBadRequest as e:
        logger.debug("Cannot edit reply markup for infinite stock: %s", e)


@router.callback_query(F.data.startswith("product_edit_"))
async def handle_product_edit(callback: CallbackQuery) -> None:
    """Handle product edit - placeholder for future implementation."""
    await callback.answer("✏️ Редактирование будет доступно в следующей версии", show_alert=True)


@router.callback_query(F.data.startswith("product_more_"))
async def handle_product_more(callback: CallbackQuery) -> None:
    """Show additional actions menu."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_more_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=product_more_keyboard(product))
    except TelegramBadRequest as e:
        logger.debug("Cannot edit reply markup for more menu: %s", e)


@router.callback_query(F.data.startswith("product_back_"))
async def handle_product_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to main product actions."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_back_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=product_actions_keyboard(product))
    except TelegramBadRequest as e:
        logger.debug("Cannot edit reply markup for back: %s", e)
