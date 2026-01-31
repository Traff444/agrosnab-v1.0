"""Writeoff (списание) handlers."""

import re
import secrets

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards import (
    cancel_keyboard,
    confirmation_keyboard,
    main_menu_keyboard,
    over_stock_keyboard,
    writeoff_reason_keyboard,
)
from app.security import confirm_store
from app.sheets import sheets_client

from .states import StockOperationState

router = Router()


@router.callback_query(F.data.startswith("product_writeoff_"))
async def start_writeoff(callback: CallbackQuery, state: FSMContext) -> None:
    """Start writeoff flow."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_writeoff_", ""))
    product = await sheets_client.get_product_by_row(row_number)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    await state.set_state(StockOperationState.writeoff_qty)
    await state.update_data(
        row_number=row_number,
        sku=product.sku,
        name=product.name,
        stock_before=product.stock,
        operation_id=secrets.token_hex(8),
    )

    await callback.message.answer(
        f"➖ **Списание: {product.name}**\n"
        f"SKU: `{product.sku}`\n"
        f"Текущий остаток: {product.stock} шт.\n\n"
        "Сколько списать?\n"
        "Примеры: `5` или `3 порча`",
        reply_markup=cancel_keyboard(),
    )


@router.message(StockOperationState.writeoff_qty, F.text, ~F.text.startswith("/"))
async def process_writeoff_qty(message: Message, state: FSMContext) -> None:
    """Process writeoff quantity input."""
    if not message.text or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()

    # Parse qty and optional reason: "5" or "3 порча"
    match = re.match(r"^(\d+)\s*(.*)$", text)
    if not match:
        await message.answer(
            "⚠️ Введите целое число.\n" "Примеры: `5` или `3 порча`"
        )
        return

    qty = int(match.group(1))
    reason = match.group(2).strip() if match.group(2) else None

    if qty <= 0:
        await message.answer("⚠️ Количество должно быть больше 0")
        return

    data = await state.get_data()
    row_number = data["row_number"]
    sku = data["sku"]

    # Re-check current stock (SKU validation)
    product = await sheets_client.get_product_by_row(row_number)
    if not product or product.sku != sku:
        await state.clear()
        await message.answer(
            "⚠️ Строка товара изменилась (таблица была отсортирована).\n"
            "Откройте карточку заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    stock_before = product.stock
    await state.update_data(stock_before=stock_before, qty=qty)

    # Check if qty exceeds stock
    if qty > stock_before:
        await message.answer(
            f"⚠️ Недостаточно товара на складе!\n\n"
            f"Остаток: {stock_before} шт.\n"
            f"Вы хотите списать: {qty} шт.",
            reply_markup=over_stock_keyboard(row_number, stock_before),
        )
        return

    # If reason provided, go to confirmation
    if reason:
        await state.update_data(reason=reason)
        await _show_writeoff_preview(message, state, message.from_user.id)
    else:
        # Ask for reason
        await state.set_state(StockOperationState.writeoff_reason)
        await message.answer(
            "Выберите причину списания:",
            reply_markup=writeoff_reason_keyboard(),
        )


@router.callback_query(F.data.startswith("writeoff_all_"))
async def handle_writeoff_all(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle 'writeoff all remaining stock' option."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("writeoff_all_", ""))
    data = await state.get_data()

    if data.get("row_number") != row_number:
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return

    stock_before = data["stock_before"]
    await state.update_data(qty=stock_before)
    await callback.answer()

    # Ask for reason
    await state.set_state(StockOperationState.writeoff_reason)
    await callback.message.answer(
        "Выберите причину списания:",
        reply_markup=writeoff_reason_keyboard(),
    )


@router.callback_query(
    StockOperationState.writeoff_reason, F.data.startswith("writeoff_reason_")
)
async def process_writeoff_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Process writeoff reason selection."""
    if not callback.data:
        return

    reason = callback.data.replace("writeoff_reason_", "")
    await callback.answer()

    if reason == "другое":
        await callback.message.answer(
            "Введите причину списания:",
            reply_markup=cancel_keyboard(),
        )
        # Stay in writeoff_reason state to accept text input
        return

    await state.update_data(reason=reason)
    await _show_writeoff_preview(callback.message, state, callback.from_user.id)


@router.message(StockOperationState.writeoff_reason, F.text, ~F.text.startswith("/"))
async def process_writeoff_reason_text(message: Message, state: FSMContext) -> None:
    """Process custom writeoff reason text."""
    if not message.text or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return

    reason = message.text.strip()[:100]  # Limit length
    await state.update_data(reason=reason)
    await _show_writeoff_preview(message, state, message.from_user.id)


async def _show_writeoff_preview(
    message: Message, state: FSMContext, user_id: int
) -> None:
    """Show writeoff preview and request confirmation."""
    data = await state.get_data()
    row_number = data["row_number"]
    sku = data["sku"]
    name = data["name"]
    qty = data["qty"]
    reason = data["reason"]

    # Re-check stock before confirmation
    product = await sheets_client.get_product_by_row(row_number)
    if not product or product.sku != sku:
        await state.clear()
        await message.answer(
            "⚠️ Строка товара изменилась. Откройте карточку заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    stock_before = product.stock
    stock_after = stock_before - qty

    if qty > stock_before:
        await message.answer(
            f"⚠️ Остаток изменился!\n"
            f"Текущий остаток: {stock_before} шт.\n"
            f"Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    await state.update_data(stock_before=stock_before)

    # Create confirmation action
    action_id = await confirm_store.create(
        action_type="stock_writeoff",
        payload={
            "row_number": row_number,
            "sku": sku,
            "qty": qty,
            "reason": reason,
            "stock_before": stock_before,
            "operation_id": data["operation_id"],
        },
        owner_id=user_id,
        ttl_seconds=300,
    )

    warning = ""
    if stock_after == 0:
        warning = "\n⚠️ **Остаток станет 0**"

    await state.set_state(StockOperationState.writeoff_confirm)
    await message.answer(
        f"📦 **Подтверждение списания**\n\n"
        f"Товар: {name} (`{sku}`)\n"
        f"Было: {stock_before} шт.\n"
        f"Списываем: {qty} шт.\n"
        f"Станет: {stock_after} шт.\n"
        f"Причина: {reason}{warning}",
        reply_markup=confirmation_keyboard(action_id),
    )
