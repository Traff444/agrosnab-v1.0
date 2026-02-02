"""Correction (корректировка) handlers."""

import secrets

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards import (
    cancel_keyboard,
    confirmation_keyboard,
    correction_reason_keyboard,
    main_menu_keyboard,
)
from app.security import confirm_store
from app.sheets import sheets_client

from .states import StockOperationState

router = Router()


@router.callback_query(F.data.startswith("product_correction_"))
async def start_correction(callback: CallbackQuery, state: FSMContext) -> None:
    """Start correction flow."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_correction_", ""))
    product = await sheets_client.get_product_by_row(row_number)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    await state.set_state(StockOperationState.correction_qty)
    await state.update_data(
        row_number=row_number,
        sku=product.sku,
        name=product.name,
        stock_before=product.stock,
        operation_id=secrets.token_hex(8),
    )

    await callback.message.answer(
        f"🧮 **Корректировка: {product.name}**\n"
        f"SKU: `{product.sku}`\n"
        f"Текущий остаток: {product.stock} шт.\n\n"
        "Введите фактический остаток.\n"
        "Пример: `37`",
        reply_markup=cancel_keyboard(),
    )


@router.message(StockOperationState.correction_qty, F.text, ~F.text.startswith("/"))
async def process_correction_qty(message: Message, state: FSMContext) -> None:
    """Process correction quantity input."""
    if not message.text or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()

    # Parse new stock value
    if not text.isdigit():
        await message.answer("⚠️ Введите целое неотрицательное число.")
        return

    new_stock = int(text)

    if new_stock < 0:
        await message.answer("⚠️ Остаток не может быть отрицательным.")
        return

    data = await state.get_data()
    row_number = data["row_number"]
    sku = data["sku"]

    # Re-check current stock (SKU validation)
    product = await sheets_client.get_product_by_row(row_number)
    if not product or product.sku != sku:
        await state.clear()
        await message.answer(
            "⚠️ Строка товара изменилась (таблица была отсортирована).\nОткройте карточку заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    stock_before = product.stock
    await state.update_data(stock_before=stock_before, new_stock=new_stock)

    # Ask for reason
    await state.set_state(StockOperationState.correction_reason)
    await message.answer(
        "Выберите причину корректировки:",
        reply_markup=correction_reason_keyboard(),
    )


@router.callback_query(
    StockOperationState.correction_reason, F.data.startswith("correction_reason_")
)
async def process_correction_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Process correction reason selection."""
    if not callback.data:
        return

    reason = callback.data.replace("correction_reason_", "")
    await callback.answer()

    if reason == "другое":
        await callback.message.answer(
            "Введите причину корректировки:",
            reply_markup=cancel_keyboard(),
        )
        return

    await state.update_data(reason=reason)
    await _show_correction_preview(callback.message, state, callback.from_user.id)


@router.message(StockOperationState.correction_reason, F.text, ~F.text.startswith("/"))
async def process_correction_reason_text(message: Message, state: FSMContext) -> None:
    """Process custom correction reason text."""
    if not message.text or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return

    reason = message.text.strip()[:100]
    await state.update_data(reason=reason)
    await _show_correction_preview(message, state, message.from_user.id)


async def _show_correction_preview(message: Message, state: FSMContext, user_id: int) -> None:
    """Show correction preview and request confirmation."""
    data = await state.get_data()
    row_number = data["row_number"]
    sku = data["sku"]
    name = data["name"]
    new_stock = data["new_stock"]
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
    delta = new_stock - stock_before

    await state.update_data(stock_before=stock_before)

    # Create confirmation action
    action_id = await confirm_store.create(
        action_type="stock_correction",
        payload={
            "row_number": row_number,
            "sku": sku,
            "new_stock": new_stock,
            "reason": reason,
            "stock_before": stock_before,
            "operation_id": data["operation_id"],
        },
        owner_id=user_id,
        ttl_seconds=300,
    )

    if delta == 0:
        delta_text = "без изменений"
    elif delta < 0:
        delta_text = f"{delta} (списание)"
    else:
        delta_text = f"+{delta} (внесение)"

    await state.set_state(StockOperationState.correction_confirm)
    await message.answer(
        f"🧮 **Подтверждение корректировки**\n\n"
        f"Товар: {name} (`{sku}`)\n"
        f"Было: {stock_before} шт.\n"
        f"Станет: {new_stock} шт.\n"
        f"Изменение: {delta_text}\n"
        f"Причина: {reason}",
        reply_markup=confirmation_keyboard(action_id),
    )
