"""Product search and management handlers."""

import re
import secrets

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    product_actions_keyboard,
    product_more_keyboard,
    confirmation_keyboard,
    writeoff_reason_keyboard,
    correction_reason_keyboard,
    archive_menu_keyboard,
    over_stock_keyboard,
    stock_operation_result_keyboard,
)
from app.services.product_service import product_service
from app.security import confirm_store
from app.sheets import sheets_client


router = Router()


class ProductState(StatesGroup):
    """FSM states for product operations."""

    searching = State()
    viewing = State()


class StockOperationState(StatesGroup):
    """FSM states for stock operations (writeoff, correction, archive)."""

    # Writeoff (Списание)
    writeoff_qty = State()
    writeoff_reason = State()
    writeoff_confirm = State()

    # Correction (Корректировка)
    correction_qty = State()
    correction_reason = State()
    correction_confirm = State()

    # Archive (Архивация)
    archive_menu = State()
    archive_confirm = State()


# -----------------------------------------------------------------------------
# Product Search
# -----------------------------------------------------------------------------


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
        await _show_product_card(message, state, product)
    else:
        # Multiple results - show list
        lines = [f"🔍 Найдено товаров: {len(result.products)}\n"]
        for p in result.products:
            status = "✅" if p.active else "❌"
            lines.append(f"{status} `{p.sku}` — {p.name} ({p.stock} шт.)")

        lines.append("\nВведите SKU для просмотра карточки.")

        await message.answer("\n".join(lines))


async def _show_product_card(
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
        await message.edit_text(card, reply_markup=product_actions_keyboard(product))
    else:
        await message.answer(card, reply_markup=product_actions_keyboard(product))


# -----------------------------------------------------------------------------
# Product Intake (Приход)
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Product Photo
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Product Edit / More Menu
# -----------------------------------------------------------------------------


@router.callback_query(F.data.startswith("product_edit_"))
async def handle_product_edit(callback: CallbackQuery) -> None:
    """Handle product edit - placeholder for future implementation."""
    await callback.answer(
        "✏️ Редактирование будет доступно в следующей версии", show_alert=True
    )


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
    await callback.message.edit_reply_markup(reply_markup=product_more_keyboard(product))


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
    await callback.message.edit_reply_markup(
        reply_markup=product_actions_keyboard(product)
    )


# -----------------------------------------------------------------------------
# Writeoff (Списание)
# -----------------------------------------------------------------------------


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
            "⚠️ Введите целое число.\n"
            "Примеры: `5` или `3 порча`"
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


async def _show_writeoff_preview(message: Message, state: FSMContext, user_id: int) -> None:
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


# -----------------------------------------------------------------------------
# Correction (Корректировка)
# -----------------------------------------------------------------------------


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
            "⚠️ Строка товара изменилась (таблица была отсортирована).\n"
            "Откройте карточку заново.",
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
async def process_correction_reason(
    callback: CallbackQuery, state: FSMContext
) -> None:
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


@router.message(
    StockOperationState.correction_reason, F.text, ~F.text.startswith("/")
)
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


# -----------------------------------------------------------------------------
# Archive (Архивация)
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Confirmation Actions
# -----------------------------------------------------------------------------


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
                f"✅ **Товар архивирован**\n\n"
                f"Остаток был 0, списание не требовалось.\n"
                f"Товар деактивирован.",
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


# -----------------------------------------------------------------------------
# Navigation callbacks
# -----------------------------------------------------------------------------


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
    await _show_product_card(callback.message, state, product, edit_message=False)


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
