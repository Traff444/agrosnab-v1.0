"""Product search handlers."""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import cancel_keyboard, main_menu_keyboard, product_actions_keyboard
from app.services.product_service import product_service

from .states import ProductState

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "🔍 Найти товар")
async def start_search(message: Message, state: FSMContext) -> None:
    """Start product search."""
    await state.set_state(ProductState.searching)
    await message.answer(
        "🔍 **Поиск товара**\n\n" "Введите SKU или название товара:",
        reply_markup=cancel_keyboard(),
    )


@router.message(ProductState.searching, F.text, ~F.text.startswith("/"))
async def process_search(message: Message, state: FSMContext) -> None:
    """Process search query."""
    if not message.text or message.text == "❌ Отмена":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=main_menu_keyboard())
        return

    query = message.text.strip()

    # Validate query length
    if len(query) > 200:
        await message.answer(
            "⚠️ Запрос слишком длинный. Максимум 200 символов.",
        )
        return

    result = await product_service.search(query)

    if not result.products:
        await message.answer(
            f"🔍 По запросу «{query}» ничего не найдено.\n\n"
            "Попробуйте другой запрос или введите точный SKU.",
        )
        return

    if len(result.products) == 1:
        # Single result - show card
        product = result.products[0]
        await show_product_card(message, state, product)
    else:
        # Multiple results - show list
        lines = [f"🔍 Найдено товаров: {len(result.products)}\n"]
        for p in result.products:
            status = "✅" if p.active else "❌"
            lines.append(f"{status} `{p.sku}` — {p.name} ({p.stock} шт.)")

        lines.append("\nВведите SKU для просмотра карточки.")

        await message.answer("\n".join(lines))


async def show_product_card(
    message: Message, state: FSMContext, product, edit_message: bool = False
) -> None:
    """Display product card with action buttons."""
    card = product_service.format_product_card(product, show_service_fields=True)

    await state.set_state(ProductState.viewing)
    await state.update_data(
        current_product_row=product.row_number,
        current_product_sku=product.sku,
    )

    if edit_message and hasattr(message, "edit_text"):
        try:
            await message.edit_text(card, reply_markup=product_actions_keyboard(product))
        except TelegramBadRequest as e:
            logger.debug("Cannot edit message for product card: %s", e)
            await message.answer(card, reply_markup=product_actions_keyboard(product))
    else:
        await message.answer(card, reply_markup=product_actions_keyboard(product))
