"""Product search and management handlers."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    product_actions_keyboard,
    confirmation_keyboard,
)
from app.services.product_service import product_service
from app.security import confirm_store


router = Router()


class ProductState(StatesGroup):
    """FSM states for product operations."""

    searching = State()
    viewing = State()


@router.message(F.text == "🔍 Найти товар")
async def start_search(message: Message, state: FSMContext) -> None:
    """Start product search."""
    await state.set_state(ProductState.searching)
    await message.answer(
        "🔍 **Поиск товара**\n\n"
        "Введите SKU или название товара:",
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
        card = product_service.format_product_card(product, show_service_fields=True)

        await state.set_state(ProductState.viewing)
        await state.update_data(current_product_row=product.row_number)

        await message.answer(
            card,
            reply_markup=product_actions_keyboard(product),
        )
    else:
        # Multiple results - show list
        lines = [f"🔍 Найдено товаров: {len(result.products)}\n"]
        for p in result.products:
            status = "✅" if p.active else "❌"
            lines.append(f"{status} `{p.sku}` — {p.name} ({p.stock} шт.)")

        lines.append("\nВведите SKU для просмотра карточки.")

        await message.answer("\n".join(lines))


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
        session = intake_service.create_session(callback.from_user.id)
        intake_service.set_existing_product(session, product)

        await state.set_state(IntakeState.waiting_for_quantity)
        await callback.message.answer(
            f"📦 Приход для **{product.name}**\n"
            f"Текущий остаток: {product.stock} шт.\n\n"
            "📊 Введите количество прихода:",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data.startswith("product_edit_"))
async def handle_product_edit(callback: CallbackQuery) -> None:
    """Handle product edit - placeholder for future implementation."""
    await callback.answer("✏️ Редактирование будет доступно в следующей версии", show_alert=True)


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
        session = intake_service.create_session(callback.from_user.id)
        intake_service.set_existing_product(session, product)
        session.quantity = 0  # No stock change

        await state.set_state(IntakeState.waiting_for_photo)
        await callback.message.answer(
            f"📷 Отправьте новое фото для **{product.name}**:",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data.startswith("product_toggle_"))
async def handle_product_toggle(callback: CallbackQuery) -> None:
    """Handle product active toggle with confirmation."""
    if not callback.data or not callback.from_user:
        return

    row_number = int(callback.data.replace("product_toggle_", ""))
    products = await product_service.get_all()
    product = next((p for p in products if p.row_number == row_number), None)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.answer()

    # Create confirmation action
    action_type = "deactivate" if product.active else "activate"
    action_id = await confirm_store.create(
        action_type=f"product_{action_type}",
        payload={"row_number": row_number, "sku": product.sku},
        owner_id=callback.from_user.id,
        ttl_seconds=300,
    )

    new_status = "деактивировать" if product.active else "активировать"
    await callback.message.answer(
        f"⚠️ **Подтверждение**\n\n"
        f"Вы уверены, что хотите {new_status} товар?\n\n"
        f"📦 {product.name}\n"
        f"SKU: `{product.sku}`",
        reply_markup=confirmation_keyboard(action_id),
    )


@router.callback_query(F.data.startswith("confirm_action_"))
async def handle_confirm_action(callback: CallbackQuery) -> None:
    """Handle confirmed action."""
    if not callback.data or not callback.from_user:
        return

    action_id = callback.data.replace("confirm_action_", "")
    action = await confirm_store.get(action_id)

    if not action:
        await callback.answer("Время подтверждения истекло", show_alert=True)
        return

    if action["owner_id"] != callback.from_user.id:
        await callback.answer("Это действие не для вас", show_alert=True)
        return

    await callback.answer()

    # Execute the action
    if action["action_type"].startswith("product_"):
        row_number = action["payload"]["row_number"]
        products = await product_service.get_all()
        product = next((p for p in products if p.row_number == row_number), None)

        if product:
            updated = await product_service.toggle_active(
                product,
                updated_by=f"tg:{callback.from_user.username or callback.from_user.id}",
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

    # Clean up action
    await confirm_store.delete(action_id)


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Handle no-op callbacks (e.g., page counter)."""
    await callback.answer()
