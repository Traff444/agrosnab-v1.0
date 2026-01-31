"""Navigation callbacks for product operations."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards import cancel_keyboard, main_menu_keyboard
from app.sheets import sheets_client

from .search import show_product_card
from .states import ProductState

router = Router()


@router.callback_query(F.data == "back_to_product")
async def handle_back_to_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to product card."""
    data = await state.get_data()
    row_number = data.get("current_product_row")

    if not row_number:
        await callback.answer()
        await callback.message.answer(
            "🔍 Используйте поиск для просмотра товара",
            reply_markup=main_menu_keyboard(),
        )
        return

    product = await sheets_client.get_product_by_row(row_number)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        await callback.message.answer(
            "🔍 Используйте поиск для просмотра товара",
            reply_markup=main_menu_keyboard(),
        )
        return

    await callback.answer()
    await show_product_card(callback.message, state, product, edit_message=False)


@router.callback_query(F.data == "start_search")
async def handle_start_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Start new search."""
    await callback.answer()
    await state.set_state(ProductState.searching)
    await callback.message.answer(
        "🔍 **Поиск товара**\n\n"
        "Введите SKU или название товара:",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Handle no-op callbacks (e.g., page counter)."""
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancel callback."""
    await callback.answer("Отменено")
    await state.clear()
    await callback.message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
