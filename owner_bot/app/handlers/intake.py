"""Intake flow handlers with FSM."""

import os
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.config import get_settings
from app.keyboards import (
    main_menu_keyboard,
    cancel_keyboard,
    confirm_cancel_keyboard,
    photo_decision_keyboard,
    photo_quality_keyboard,
    product_match_keyboard,
    retry_keyboard,
)
from app.models import IntakeConfidence, PhotoStatus
from app.services.intake_service import intake_service
from app.services.product_service import product_service
from app.intake_parser import format_parsed_intake
from app.photo_quality import format_quality_report
from app.photo_enhance import format_enhance_report


router = Router()


class IntakeState(StatesGroup):
    """FSM states for intake flow."""

    waiting_for_input = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_quantity = State()
    waiting_for_match_decision = State()
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
    session = intake_service.create_session(message.from_user.id)

    await state.set_state(IntakeState.waiting_for_input)
    await message.answer(
        "📦 **Приход товара**\n\n"
        "Введите данные одним сообщением:\n"
        "`Название Цена Количество`\n\n"
        "Пример: `Махорка СССР 500 10`\n\n"
        "Или просто название товара для пошагового ввода.",
        reply_markup=cancel_keyboard(),
    )


@router.message(IntakeState.waiting_for_input, F.text, ~F.text.startswith("/"), ~F.text.in_({"❌ Отмена"}))
async def process_input(message: Message, state: FSMContext) -> None:
    """Process initial input (quick string or name)."""
    if not message.from_user or not message.text:
        return

    session = intake_service.get_session(message.from_user.id)
    if not session:
        session = intake_service.create_session(message.from_user.id)

    parsed = intake_service.parse_quick_string(message.text)
    intake_service.update_session_from_parsed(session, parsed)

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

    session = intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    session.name = message.text.strip()

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

    session = intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    try:
        price = float(message.text.replace(",", ".").replace("₽", "").replace("р", "").strip())
        if price <= 0:
            raise ValueError("Price must be positive")
        session.price = price
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

    session = intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    try:
        qty = int(message.text.replace("шт", "").replace(".", "").strip())
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        session.quantity = qty
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
        # No matches - create new product
        intake_service.set_new_product(session)
        await _ask_photo_decision(message, state, session)


@router.callback_query(IntakeState.waiting_for_match_decision, F.data.startswith("match_"))
async def process_match_decision(callback: CallbackQuery, state: FSMContext) -> None:
    """Process product match selection."""
    if not callback.from_user or not callback.data:
        return

    session = intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    if callback.data == "match_new":
        intake_service.set_new_product(session)
        await _ask_photo_decision(callback.message, state, session)
    else:
        # Selected existing product
        row_number = int(callback.data.replace("match_", ""))
        products = await product_service.get_all()
        product = next((p for p in products if p.row_number == row_number), None)

        if not product:
            await callback.message.answer("❌ Товар не найден")
            return

        intake_service.set_existing_product(session, product)
        await _ask_photo_decision(callback.message, state, session)


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

    session = intake_service.get_session(callback.from_user.id)
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

    session = intake_service.get_session(message.from_user.id)
    if not session:
        await _restart_intake(message, state)
        return

    settings = get_settings()

    # Get largest photo
    photo = message.photo[-1]
    session.photo_file_id = photo.file_id

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


@router.callback_query(IntakeState.photo_review)
async def process_photo_review(callback: CallbackQuery, state: FSMContext) -> None:
    """Process photo quality review decision."""
    if not callback.from_user or not callback.data:
        return

    session = intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()
    data = await state.get_data()
    tmp_path = data.get("tmp_path")

    if callback.data == "photo_accept":
        # Upload as-is
        if tmp_path:
            result = await intake_service.upload_photo(session, tmp_path)
            if not result.permissions_ok:
                await callback.message.answer(
                    f"⚠️ Фото загружено, но не удалось установить публичный доступ:\n"
                    f"{result.error_message}"
                )
            # Clean up tmp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        await _show_preview(callback.message, state, session)

    elif callback.data == "photo_enhance":
        # Enhance and show result
        if tmp_path:
            enhanced_path = await intake_service.enhance_photo(tmp_path)
            from app.photo_enhance import enhance_photo

            result = enhance_photo(tmp_path)
            await callback.message.answer(format_enhance_report(result))

            # Re-analyze enhanced photo
            quality = await intake_service.download_and_analyze_photo(session, enhanced_path)
            await state.update_data(tmp_path=enhanced_path)

            await callback.message.answer(
                format_quality_report(quality),
                reply_markup=photo_quality_keyboard(quality.status.value),
            )

    elif callback.data == "photo_retake":
        # Clean up and ask for new photo
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        session.photo_file_id = None
        session.photo_quality = None
        await state.set_state(IntakeState.waiting_for_photo)
        await callback.message.answer(
            "📷 Отправьте новое фото товара:",
            reply_markup=cancel_keyboard(),
        )

    elif callback.data == "cancel":
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
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

    session = intake_service.get_session(callback.from_user.id)
    if not session:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    if callback.data == "confirm":
        # Execute the intake
        username = callback.from_user.username or str(callback.from_user.id)
        result = await intake_service.complete_intake(session, updated_by=f"tg:{username}")

        if result.success:
            action = "создан" if result.is_new else "обновлён"
            card = product_service.format_product_card(result.product, show_service_fields=True)

            await callback.message.answer(
                f"✅ Товар {action}!\n\n{card}",
                reply_markup=main_menu_keyboard(),
            )

            # Clean up session
            intake_service.clear_session(callback.from_user.id)
            await state.clear()
        else:
            # Error - offer retry
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

    session = intake_service.get_session(callback.from_user.id)
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

        intake_service.clear_session(callback.from_user.id)
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
        intake_service.clear_session(callback.from_user.id)

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
