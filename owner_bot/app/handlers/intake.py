"""Intake flow handlers with FSM."""

import contextlib
import logging
import os
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import get_settings
from app.intake_parser import format_parsed_intake
from app.keyboards import (
    cancel_keyboard,
    confirm_cancel_keyboard,
    main_menu_keyboard,
    photo_decision_keyboard,
    photo_quality_keyboard,
    product_match_keyboard,
    quick_weight_keyboard,
    retry_keyboard,
    skip_weight_keyboard,
)
from app.models import IntakeConfidence
from app.photo_enhance import format_enhance_report
from app.photo_quality import format_quality_report
from app.services.intake_service import intake_service
from app.services.product_service import product_service

logger = logging.getLogger(__name__)
router = Router()


class IntakeState(StatesGroup):
    """FSM states for intake flow."""

    waiting_for_input = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_quantity = State()
    waiting_for_match_decision = State()
    waiting_for_weight = State()
    waiting_for_photo_decision = State()
    waiting_for_photo = State()
    photo_review = State()
    preview_confirm = State()
    retry_sheets_write = State()


@router.message(F.text == "📦 Приход товара")
async def start_intake(message: Message, state: FSMContext) -> None:
    """Start intake flow."""
    if not message.from_user:
        return

    # Create new session
    await intake_service.create_session(message.from_user.id)

    await state.set_state(IntakeState.waiting_for_input)
    await message.answer(
        "📦 **Приход товара**\n\n"
        "Введите данные одним сообщением:\n"
        "`Название [Вес] Цена Количество`\n\n"
        "Примеры:\n"
        "• `Махорка СССР 50г 500 10`\n"
        "• `Махорка СССР 500 10` (без веса)\n\n"
        "Или просто название товара для пошагового ввода.",
        reply_markup=cancel_keyboard(),
    )


@router.message(IntakeState.waiting_for_input, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_input(message: Message, state: FSMContext) -> None:
    """Process initial input (quick string or name)."""
    if not message.from_user or not message.text:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        session = await intake_service.create_session(message.from_user.id)

    parsed = intake_service.parse_quick_string(message.text)
    await intake_service.update_session_from_parsed(session, parsed)

    # Show what was parsed
    await message.answer(format_parsed_intake(parsed))

    if parsed.confidence == IntakeConfidence.HIGH:
        # High confidence - look for matching products
        await _check_matching_products(message, state, session)
    else:
        # Low confidence - ask for missing fields
        if not session.name:
            await state.set_state(IntakeState.waiting_for_name)
            await message.answer("📦 Введите название товара:")
        elif session.price is None:
            await state.set_state(IntakeState.waiting_for_price)
            await message.answer("💰 Введите цену товара (в рублях):")
        elif session.quantity is None:
            await state.set_state(IntakeState.waiting_for_quantity)
            await message.answer("📊 Введите количество:")
        else:
            await _check_matching_products(message, state, session)


@router.message(IntakeState.waiting_for_name, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_name(message: Message, state: FSMContext) -> None:
    """Process product name input."""
    if not message.from_user or not message.text:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    session.name = message.text.strip()
    await intake_service.save_session(session)

    if session.price is None:
        await state.set_state(IntakeState.waiting_for_price)
        await message.answer("💰 Введите цену товара (в рублях):")
    elif session.quantity is None:
        await state.set_state(IntakeState.waiting_for_quantity)
        await message.answer("📊 Введите количество:")
    else:
        await _check_matching_products(message, state, session)


@router.message(IntakeState.waiting_for_price, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_price(message: Message, state: FSMContext) -> None:
    """Process price input."""
    if not message.from_user or not message.text:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    try:
        price = float(message.text.replace(",", ".").replace("₽", "").replace("р", "").strip())
        if price <= 0:
            raise ValueError("Price must be positive")
        session.price = price
        await intake_service.save_session(session)
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число:")
        return

    if session.quantity is None:
        await state.set_state(IntakeState.waiting_for_quantity)
        await message.answer("📊 Введите количество:")
    else:
        await _check_matching_products(message, state, session)


@router.message(IntakeState.waiting_for_quantity, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_quantity(message: Message, state: FSMContext) -> None:
    """Process quantity input."""
    if not message.from_user or not message.text:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    try:
        qty = int(message.text.replace("шт", "").replace(".", "").strip())
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        session.quantity = qty
        await intake_service.save_session(session)
    except ValueError:
        await message.answer("❌ Неверный формат количества. Введите целое число:")
        return

    await _check_matching_products(message, state, session)


async def _check_matching_products(message: Message, state: FSMContext, session) -> None:
    """Check for matching products and show options."""
    if not session.name:
        await state.set_state(IntakeState.waiting_for_name)
        await message.answer("📦 Введите название товара:")
        return

    matches = await intake_service.find_matching_products(session.name)

    if matches:
        await state.set_state(IntakeState.waiting_for_match_decision)
        await message.answer(
            f"🔍 Найдено похожих товаров: {len(matches)}\n\n"
            "Выберите существующий или создайте новый:",
            reply_markup=product_match_keyboard(matches),
        )
    else:
        # No matches - create new product, ask for weight first
        await intake_service.set_new_product(session)
        await _ask_weight(message, state, session)


@router.callback_query(IntakeState.waiting_for_match_decision, F.data.startswith("match_"))
async def process_match_decision(callback: CallbackQuery, state: FSMContext) -> None:
    """Process product match selection."""
    if not callback.from_user or not callback.data:
        return

    logger.debug("process_match_decision: user=%s, data=%s", callback.from_user.id, callback.data)

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    if callback.data == "match_new":
        logger.debug("process_match_decision: creating NEW product")
        await intake_service.set_new_product(session)
        # For new products, ask for weight first
        await _ask_weight(callback.message, state, session)
    else:
        # Selected existing product
        row_number = int(callback.data.replace("match_", ""))
        logger.debug("process_match_decision: selected EXISTING product row=%d", row_number)
        products = await product_service.get_all()
        product = next((p for p in products if p.row_number == row_number), None)

        if not product:
            await callback.message.answer("❌ Товар не найден")
            return

        await intake_service.set_existing_product(session, product)
        logger.debug("process_match_decision: set existing_product SKU=%s", product.sku)
        # Existing products already have weight in the table
        await _ask_photo_decision(callback.message, state, session)


async def _ask_weight(message: Message, state: FSMContext, session) -> None:
    """Ask for package weight (optional, only for new products)."""
    # If weight was already parsed from quick-string, skip this step
    if session.package_weight is not None:
        await _ask_photo_decision(message, state, session)
        return

    await state.set_state(IntakeState.waiting_for_weight)
    await message.answer(
        "⚖️ Выберите вес упаковки:",
        reply_markup=quick_weight_keyboard(),
    )


@router.callback_query(IntakeState.waiting_for_weight, F.data == "skip_weight")
async def skip_weight(callback: CallbackQuery, state: FSMContext) -> None:
    """Skip weight input."""
    if not callback.from_user:
        return

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    session.package_weight = None
    await intake_service.save_session(session)
    await callback.answer()
    await _ask_photo_decision(callback.message, state, session)


@router.callback_query(IntakeState.waiting_for_weight, F.data.startswith("quick_weight:"))
async def handle_quick_weight(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle quick weight selection buttons."""
    if not callback.from_user or not callback.data:
        return

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    # Extract weight value from callback_data
    weight_value = callback.data.split(":")[1]

    if weight_value == "skip":
        # Skip weight - proceed without it
        session.package_weight = None
        await intake_service.save_session(session)
        await _ask_photo_decision(callback.message, state, session)
    elif weight_value == "custom":
        # Custom weight - ask for manual input
        await callback.message.answer(
            "⚖️ Введите вес упаковки в граммах:",
            reply_markup=skip_weight_keyboard(),
        )
    else:
        # Numeric weight selected
        session.package_weight = int(weight_value)
        await intake_service.save_session(session)
        await _ask_photo_decision(callback.message, state, session)


@router.message(IntakeState.waiting_for_weight, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_weight(message: Message, state: FSMContext) -> None:
    """Process weight input."""
    if not message.from_user or not message.text:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    try:
        # Remove common weight suffixes
        weight_text = message.text.replace("г", "").replace("гр", "").replace("g", "").strip()
        weight = int(weight_text)
        if weight <= 0:
            raise ValueError("Weight must be positive")
        if weight > 100000:  # 100kg max reasonable package weight
            raise ValueError("Weight exceeds maximum")
        session.package_weight = weight
    except ValueError:
        await message.answer(
            "❌ Введите целое число (в граммах) или нажмите Пропустить:",
            reply_markup=skip_weight_keyboard(),
        )
        return

    await intake_service.save_session(session)
    await _ask_photo_decision(message, state, session)


async def _ask_photo_decision(message: Message, state: FSMContext, session) -> None:
    """Ask about photo upload."""
    has_photo = bool(
        session.existing_product and session.existing_product.photo_url
    )

    await state.set_state(IntakeState.waiting_for_photo_decision)

    if session.is_new_product:
        text = "📷 Добавить фото для нового товара?"
    else:
        if has_photo:
            text = "📷 У товара уже есть фото. Заменить?"
        else:
            text = "📷 У товара нет фото. Добавить?"

    await message.answer(text, reply_markup=photo_decision_keyboard(has_photo))


@router.callback_query(IntakeState.waiting_for_photo_decision)
async def process_photo_decision(callback: CallbackQuery, state: FSMContext) -> None:
    """Process photo decision."""
    if not callback.from_user or not callback.data:
        return

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    if callback.data in ("photo_replace", "photo_add"):
        await state.set_state(IntakeState.waiting_for_photo)
        await callback.message.answer(
            "📷 Отправьте фото товара:",
            reply_markup=cancel_keyboard(),
        )
    elif callback.data in ("photo_keep", "photo_skip"):
        await _show_preview(callback.message, state, session)
    elif callback.data == "cancel":
        await _cancel_intake(callback, state)


@router.message(IntakeState.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Process uploaded photo."""
    if not message.from_user or not message.photo:
        return

    session = await intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    settings = get_settings()

    # Get largest photo
    photo = message.photo[-1]
    session.photo_file_id = photo.file_id
    await intake_service.save_session(session)

    # Download photo to tmp
    tmp_dir = Path(settings.tmp_dir)
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f"{message.from_user.id}_{photo.file_id}.jpg"

    file = await bot.get_file(photo.file_id)
    await bot.download_file(file.file_path, tmp_path)

    # Analyze quality
    quality = await intake_service.download_and_analyze_photo(session, str(tmp_path))

    await state.set_state(IntakeState.photo_review)
    await state.update_data(tmp_path=str(tmp_path))

    await message.answer(
        format_quality_report(quality),
        reply_markup=photo_quality_keyboard(quality.status.value),
    )


async def _handle_photo_accept(
    callback: CallbackQuery, state: FSMContext, session, tmp_path: str | None
) -> None:
    """Handle photo accept action - upload as-is."""
    if tmp_path:
        result = await intake_service.upload_photo(session, tmp_path)
        if not result.permissions_ok:
            await callback.message.answer(
                f"⚠️ Фото загружено, но не удалось установить публичный доступ:\n"
                f"{result.error_message}"
            )
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
    await _show_preview(callback.message, state, session)


async def _handle_photo_enhance(
    callback: CallbackQuery, state: FSMContext, session, tmp_path: str | None
) -> None:
    """Handle photo enhance action - improve and re-analyze."""
    if not tmp_path:
        return

    enhanced_path = await intake_service.enhance_photo(tmp_path)
    from app.photo_enhance import enhance_photo

    result = enhance_photo(tmp_path)
    await callback.message.answer(format_enhance_report(result))

    quality = await intake_service.download_and_analyze_photo(session, enhanced_path)
    await state.update_data(tmp_path=enhanced_path)

    await callback.message.answer(
        format_quality_report(quality),
        reply_markup=photo_quality_keyboard(quality.status.value),
    )


async def _handle_photo_retake(
    callback: CallbackQuery, state: FSMContext, session, tmp_path: str | None
) -> None:
    """Handle photo retake action - clean up and ask for new photo."""
    if tmp_path:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
    session.photo_file_id = None
    session.photo_quality = None
    await intake_service.save_session(session)
    await state.set_state(IntakeState.waiting_for_photo)
    await callback.message.answer(
        "📷 Отправьте новое фото товара:",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(IntakeState.photo_review)
async def process_photo_review(callback: CallbackQuery, state: FSMContext) -> None:
    """Process photo quality review decision."""
    if not callback.from_user or not callback.data:
        return

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()
    data = await state.get_data()
    tmp_path = data.get("tmp_path")

    if callback.data == "photo_accept":
        await _handle_photo_accept(callback, state, session, tmp_path)
    elif callback.data == "photo_enhance":
        await _handle_photo_enhance(callback, state, session, tmp_path)
    elif callback.data == "photo_retake":
        await _handle_photo_retake(callback, state, session, tmp_path)
    elif callback.data == "cancel":
        if tmp_path:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
        await _cancel_intake(callback, state)


async def _show_preview(message: Message, state: FSMContext, session) -> None:
    """Show intake preview for confirmation."""
    preview = intake_service.format_session_preview(session)

    await state.set_state(IntakeState.preview_confirm)

    # Если есть фото - отправить с caption
    if session.drive_url:
        await message.answer_photo(
            photo=session.drive_url,
            caption=preview + "\n\n**Подтвердить приход?**",
            reply_markup=confirm_cancel_keyboard(),
        )
    else:
        await message.answer(
            preview + "\n\n**Подтвердить приход?**",
            reply_markup=confirm_cancel_keyboard(),
        )


@router.callback_query(IntakeState.preview_confirm)
async def process_preview_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Process preview confirmation."""
    if not callback.from_user or not callback.data:
        return

    logger.debug("process_preview_confirm: user=%s, data=%s", callback.from_user.id, callback.data)

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        logger.warning("process_preview_confirm: session not found!")
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    logger.debug(
        "process_preview_confirm: session found, is_new=%s, name=%s, qty=%s, drive_url=%s",
        session.is_new_product, session.name, session.quantity, session.drive_url
    )

    await callback.answer()

    if callback.data == "confirm":
        logger.debug("process_preview_confirm: user confirmed, calling complete_intake")
        # Execute the intake
        username = callback.from_user.username or str(callback.from_user.id)
        result = await intake_service.complete_intake(session, updated_by=f"tg:{username}")

        logger.debug(
            "process_preview_confirm: result.success=%s, is_new=%s, error=%s",
            result.success, result.is_new, result.error
        )

        if result.success:
            action = "создан" if result.is_new else "обновлён"
            logger.debug("process_preview_confirm: SUCCESS - product %s", action)
            card = product_service.format_product_card(result.product, show_service_fields=True)

            await callback.message.answer(
                f"✅ Товар {action}!\n\n{card}",
                reply_markup=main_menu_keyboard(),
            )

            # Clean up session
            await intake_service.clear_session(callback.from_user.id)
            await state.clear()
        else:
            # Error - offer retry
            logger.error("process_preview_confirm: FAILED - %s", result.error)
            await state.set_state(IntakeState.retry_sheets_write)
            await callback.message.answer(
                f"❌ Ошибка записи в Google Sheets:\n{result.error}\n\n"
                "Данные сохранены. Повторить попытку?",
                reply_markup=retry_keyboard("sheets_write"),
            )

    elif callback.data == "cancel":
        await _cancel_intake(callback, state)


@router.callback_query(IntakeState.retry_sheets_write, F.data.startswith("retry_"))
async def process_retry(callback: CallbackQuery, state: FSMContext) -> None:
    """Process retry action."""
    if not callback.from_user:
        return

    session = await intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    username = callback.from_user.username or str(callback.from_user.id)
    result = await intake_service.complete_intake(session, updated_by=f"tg:{username}")

    if result.success:
        action = "создан" if result.is_new else "обновлён"
        card = product_service.format_product_card(result.product, show_service_fields=True)

        await callback.message.answer(
            f"✅ Товар {action}!\n\n{card}",
            reply_markup=main_menu_keyboard(),
        )

        await intake_service.clear_session(callback.from_user.id)
        await state.clear()
    else:
        await callback.message.answer(
            f"❌ Повторная ошибка:\n{result.error}",
            reply_markup=retry_keyboard("sheets_write"),
        )


@router.callback_query(F.data == "cancel")
async def process_cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle cancel callback from any state."""
    await _cancel_intake(callback, state)


async def _cancel_intake(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel intake and return to menu."""
    if callback.from_user:
        await intake_service.clear_session(callback.from_user.id)

    await state.clear()
    await callback.message.answer(
        "🏠 Приход отменён. Возврат в главное меню.",
        reply_markup=main_menu_keyboard(),
    )


async def _restart_intake(message: Message, state: FSMContext) -> None:
    """Restart intake flow due to session loss."""
    await state.clear()
    await message.answer(
        "⚠️ Сессия истекла. Начните приход заново.",
        reply_markup=main_menu_keyboard(),
    )
