"""Stock listing handlers."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.keyboards import (
    stock_list_keyboard,
    main_menu_keyboard,
    product_actions_keyboard,
)
from app.sheets import sheets_client
from app.services.product_service import product_service

router = Router()

ITEMS_PER_PAGE = 8


@router.message(F.text == "📊 Склад")
async def show_stock(message: Message, state: FSMContext) -> None:
    """Show all products with pagination."""
    products = await sheets_client.get_all_products()

    if not products:
        await message.answer("📦 Склад пуст", reply_markup=main_menu_keyboard())
        return

    products.sort(key=lambda p: (not p.active, p.name.lower()))

    total_pages = (len(products) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page_products = products[:ITEMS_PER_PAGE]

    await state.update_data(
        stock_products=[p.row_number for p in products],
        stock_page=1,
    )

    active_count = sum(1 for p in products if p.active)
    total_stock = sum(p.stock for p in products if p.active)

    text = (
        f"📊 **Склад** — {len(products)} товаров\n"
        f"✅ Активных: {active_count} | 📦 Всего: {total_stock} шт.\n\n"
        "Выберите товар:"
    )

    await message.answer(
        text,
        reply_markup=stock_list_keyboard(page_products, 1, total_pages),
    )


@router.callback_query(F.data.startswith("stock_page_"))
async def stock_page(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle pagination."""
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    row_numbers = data.get("stock_products", [])

    all_products = await sheets_client.get_all_products()
    products = [p for p in all_products if p.row_number in row_numbers]
    products.sort(key=lambda p: (not p.active, p.name.lower()))

    total_pages = (len(products) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start = (page - 1) * ITEMS_PER_PAGE
    page_products = products[start:start + ITEMS_PER_PAGE]

    await state.update_data(stock_page=page)

    active_count = sum(1 for p in products if p.active)
    total_stock = sum(p.stock for p in products if p.active)

    text = (
        f"📊 **Склад** — {len(products)} товаров\n"
        f"✅ Активных: {active_count} | 📦 Всего: {total_stock} шт.\n\n"
        "Выберите товар:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=stock_list_keyboard(page_products, page, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stock_select_"))
async def stock_select(callback: CallbackQuery, state: FSMContext) -> None:
    """Select product from stock list."""
    row_number = int(callback.data.split("_")[-1])

    product = await sheets_client.get_product_by_row(row_number)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    card = product_service.format_product_card(product, show_service_fields=True)

    await state.update_data(
        current_product_row=product.row_number,
        current_product_sku=product.sku,
    )

    await callback.message.edit_text(
        card,
        reply_markup=product_actions_keyboard(product),
    )
    await callback.answer()


@router.callback_query(F.data == "stock_close")
async def stock_close(callback: CallbackQuery, state: FSMContext) -> None:
    """Close stock list."""
    await callback.message.delete()
    await callback.answer()
