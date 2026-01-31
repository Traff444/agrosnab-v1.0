"""Archive (архивация) handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards import (
    archive_menu_keyboard,
    confirmation_keyboard,
)
from app.security import confirm_store
from app.sheets import sheets_client

from .states import StockOperationState

router = Router()


@router.callback_query(F.data.startswith("product_archive_"))
async def show_archive_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show archive options menu."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("product_archive_", ""))
    product = await sheets_client.get_product_by_row(row_number)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    await state.set_state(StockOperationState.archive_menu)
    await state.update_data(
        row_number=row_number,
        sku=product.sku,
        name=product.name,
        stock_before=product.stock,
    )

    await callback.message.answer(
        f"🗑️ **Архивация: {product.name}**\n"
        f"SKU: `{product.sku}`\n"
        f"Текущий остаток: {product.stock} шт.\n\n"
        "Выберите действие:",
        reply_markup=archive_menu_keyboard(row_number),
    )


@router.callback_query(
    StockOperationState.archive_menu, F.data.startswith("archive_simple_")
)
async def handle_archive_simple(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle simple archive (deactivate only, no stock change)."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("archive_simple_", ""))
    data = await state.get_data()

    if data.get("row_number") != row_number:
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return

    sku = data["sku"]
    name = data["name"]

    # Create confirmation action
    action_id = await confirm_store.create(
        action_type="archive_simple",
        payload={
            "row_number": row_number,
            "sku": sku,
        },
        owner_id=callback.from_user.id if callback.from_user else 0,
        ttl_seconds=300,
    )

    await callback.answer()
    await state.set_state(StockOperationState.archive_confirm)
    await callback.message.answer(
        f"🗑️ **Подтверждение архивации**\n\n"
        f"Товар: {name} (`{sku}`)\n\n"
        "Товар будет деактивирован (убран из каталога).\n"
        "Остаток не изменится.",
        reply_markup=confirmation_keyboard(action_id),
    )


@router.callback_query(
    StockOperationState.archive_menu, F.data.startswith("archive_zero_")
)
async def handle_archive_zero(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle archive with zero out (writeoff remaining stock + deactivate)."""
    if not callback.data:
        return

    row_number = int(callback.data.replace("archive_zero_", ""))
    data = await state.get_data()

    if data.get("row_number") != row_number:
        await callback.answer("Сессия устарела", show_alert=True)
        await state.clear()
        return

    sku = data["sku"]
    name = data["name"]
    stock_before = data["stock_before"]

    # Create confirmation action
    action_id = await confirm_store.create(
        action_type="archive_zero_out",
        payload={
            "row_number": row_number,
            "sku": sku,
            "stock_before": stock_before,
        },
        owner_id=callback.from_user.id if callback.from_user else 0,
        ttl_seconds=300,
    )

    await callback.answer()
    await state.set_state(StockOperationState.archive_confirm)

    stock_note = ""
    if stock_before > 0:
        stock_note = f"\n⚠️ Остаток {stock_before} шт. будет списан и записан в журнал."
    else:
        stock_note = "\nОстаток уже 0, списание не требуется."

    await callback.message.answer(
        f"🧹 **Подтверждение архивации с обнулением**\n\n"
        f"Товар: {name} (`{sku}`){stock_note}",
        reply_markup=confirmation_keyboard(action_id),
    )
