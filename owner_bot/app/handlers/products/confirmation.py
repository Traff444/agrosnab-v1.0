"""Confirmation action handlers for stock operations."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards import (
    main_menu_keyboard,
    stock_operation_result_keyboard,
)
from app.security import confirm_store
from app.services.product_service import product_service
from app.sheets import sheets_client

router = Router()


@router.callback_query(F.data.startswith("confirm_action_"))
async def handle_confirm_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle confirmed action."""
    if not callback.data or not callback.from_user:
        return

    action_id = callback.data.replace("confirm_action_", "")
    action = await confirm_store.get(action_id)

    if not action:
        await callback.answer("Время подтверждения истекло", show_alert=True)
        await state.clear()
        return

    if action["owner_id"] != callback.from_user.id:
        await callback.answer("Это действие не для вас", show_alert=True)
        return

    await callback.answer("⏳ Выполняем...")

    action_type = action["action_type"]
    payload = action["payload"]
    actor_username = callback.from_user.username or str(callback.from_user.id)

    # Clean up action
    await confirm_store.delete(action_id)

    # Execute based on action type
    if action_type == "stock_writeoff":
        await _execute_writeoff(callback, state, payload, actor_username)

    elif action_type == "stock_correction":
        await _execute_correction(callback, state, payload, actor_username)

    elif action_type == "archive_simple":
        await _execute_archive_simple(callback, state, payload, actor_username)

    elif action_type == "archive_zero_out":
        await _execute_archive_zero_out(callback, state, payload, actor_username)

    elif action_type.startswith("product_"):
        # Legacy product activate/deactivate
        await _execute_product_toggle(callback, state, action_type, payload, actor_username)


async def _execute_writeoff(
    callback: CallbackQuery,
    state: FSMContext,
    payload: dict,
    actor_username: str,
) -> None:
    """Execute writeoff operation."""
    result = await sheets_client.apply_writeoff(
        row_number=payload["row_number"],
        qty=payload["qty"],
        reason=payload["reason"],
        actor_id=callback.from_user.id,
        actor_username=actor_username,
        operation_id=payload.get("operation_id"),
    )

    await state.clear()

    if result.ok:
        await callback.message.answer(
            f"✅ **Списание выполнено**\n\n"
            f"Было: {result.stock_before} шт.\n"
            f"Списано: {payload['qty']} шт.\n"
            f"Остаток: {result.stock_after} шт.",
            reply_markup=stock_operation_result_keyboard(),
        )
    else:
        await callback.message.answer(
            f"❌ **Ошибка списания**\n\n{result.error}",
            reply_markup=main_menu_keyboard(),
        )


async def _execute_correction(
    callback: CallbackQuery,
    state: FSMContext,
    payload: dict,
    actor_username: str,
) -> None:
    """Execute correction operation."""
    result = await sheets_client.apply_correction(
        row_number=payload["row_number"],
        new_stock=payload["new_stock"],
        reason=payload["reason"],
        actor_id=callback.from_user.id,
        actor_username=actor_username,
        operation_id=payload.get("operation_id"),
    )

    await state.clear()

    if result.ok:
        delta = result.stock_after - result.stock_before
        if delta == 0:
            delta_text = "без изменений"
        elif delta < 0:
            delta_text = f"{delta} (списано)"
        else:
            delta_text = f"+{delta} (внесено)"

        await callback.message.answer(
            f"✅ **Корректировка выполнена**\n\n"
            f"Было: {result.stock_before} шт.\n"
            f"Стало: {result.stock_after} шт.\n"
            f"Изменение: {delta_text}",
            reply_markup=stock_operation_result_keyboard(),
        )
    else:
        await callback.message.answer(
            f"❌ **Ошибка корректировки**\n\n{result.error}",
            reply_markup=main_menu_keyboard(),
        )


async def _execute_archive_simple(
    callback: CallbackQuery,
    state: FSMContext,
    payload: dict,
    actor_username: str,
) -> None:
    """Execute simple archive (deactivate only)."""
    row_number = payload["row_number"]
    sku = payload["sku"]

    # Verify SKU hasn't changed
    product = await sheets_client.get_product_by_row(row_number)
    if not product or product.sku != sku:
        await state.clear()
        await callback.message.answer(
            "⚠️ Строка товара изменилась. Откройте карточку заново.",
            reply_markup=main_menu_keyboard(),
        )
        return

    try:
        await sheets_client.update_product_active(
            product=product,
            active=False,
            updated_by=f"tg:{actor_username}",
        )

        await state.clear()
        await callback.message.answer(
            f"✅ **Товар архивирован**\n\n"
            f"Товар убран из каталога.\n"
            f"Остаток не изменён: {product.stock} шт.",
            reply_markup=stock_operation_result_keyboard(),
        )

    except Exception as e:
        await state.clear()
        await callback.message.answer(
            f"❌ **Ошибка архивации**\n\n{e}",
            reply_markup=main_menu_keyboard(),
        )


async def _execute_archive_zero_out(
    callback: CallbackQuery,
    state: FSMContext,
    payload: dict,
    actor_username: str,
) -> None:
    """Execute archive with zero out."""
    result = await sheets_client.apply_archive_zero_out(
        row_number=payload["row_number"],
        actor_id=callback.from_user.id,
        actor_username=actor_username,
    )

    await state.clear()

    if result.ok:
        if result.stock_before > 0:
            await callback.message.answer(
                f"✅ **Товар архивирован с обнулением**\n\n"
                f"Списано: {result.stock_before} шт.\n"
                f"Остаток: 0 шт.\n"
                f"Товар деактивирован.",
                reply_markup=stock_operation_result_keyboard(),
            )
        else:
            await callback.message.answer(
                "✅ **Товар архивирован**\n\n"
                "Остаток был 0, списание не требовалось.\n"
                "Товар деактивирован.",
                reply_markup=stock_operation_result_keyboard(),
            )
    else:
        await callback.message.answer(
            f"❌ **Ошибка архивации**\n\n{result.error}",
            reply_markup=main_menu_keyboard(),
        )


async def _execute_product_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    action_type: str,
    payload: dict,
    actor_username: str,
) -> None:
    """Execute legacy product activate/deactivate."""
    row_number = payload["row_number"]
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if product:
        updated = await product_service.toggle_active(
            product,
            updated_by=f"tg:{actor_username}",
        )
        status = "активирован" if updated.active else "деактивирован"
        await callback.message.answer(
            f"✅ Товар {status}!\n\n"
            f"📦 {updated.name}\n"
            f"SKU: `{updated.sku}`",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await callback.message.answer(
            "❌ Товар не найден",
            reply_markup=main_menu_keyboard(),
        )
