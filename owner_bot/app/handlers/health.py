"""Health check and status handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.drive import drive_client
from app.keyboards import main_menu_keyboard
from app.photo_enhance import cleanup_tmp_files
from app.security import confirm_store
from app.sheets import sheets_client

router = Router()


@router.message(F.text == "🔧 Статус")
async def show_status(message: Message, state: FSMContext) -> None:
    """Show system status and health checks."""
    await state.clear()  # Clear FSM state to avoid conflicts with intake flow
    await message.answer("🔍 Проверяю подключения...")

    # Run checks in parallel-ish manner
    sheets_status = await sheets_client.test_connection()
    drive_status = await drive_client.test_connection()

    lines = ["🔧 Статус системы\n"]

    # Google Sheets status
    if sheets_status.get("ok"):
        lines.append("✅ Google Sheets")
        lines.append(f"   Таблица: {sheets_status.get('spreadsheet_title', 'N/A')}")
        lines.append(f"   Листы: {', '.join(sheets_status.get('sheets', []))}")
        cols = sheets_status.get("columns_found", [])
        if cols:
            lines.append(f"   Колонки: {len(cols)} найдено")
    else:
        lines.append("❌ Google Sheets")
        error = sheets_status.get("error", "Неизвестная ошибка")
        lines.append(f"   Ошибка: {error}")

        missing = sheets_status.get("missing_columns", [])
        if missing:
            lines.append(f"   Отсутствуют колонки: {', '.join(missing)}")

    lines.append("")

    # Google Drive status
    if drive_status.get("ok"):
        lines.append("✅ Google Drive")
        lines.append(f"   Папка: {drive_status.get('folder_name', 'N/A')}")
    else:
        lines.append("❌ Google Drive")
        lines.append(f"   Ошибка: {drive_status.get('error', 'Неизвестная ошибка')}")

    lines.append("")

    # Cleanup option
    lines.append("🧹 Для очистки временных файлов используйте /cleanup")

    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard(), parse_mode=None)


@router.message(F.text == "/cleanup")
async def request_cleanup(message: Message) -> None:
    """Request temp files cleanup."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="cleanup_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await message.answer(
        "🧹 Очистка временных файлов\n\n"
        "Будут удалены временные файлы старше 24 часов.\n"
        "Подтвердить?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "cleanup_confirm")
async def confirm_cleanup(callback: CallbackQuery) -> None:
    """Confirm and execute cleanup."""
    await callback.answer()

    deleted_files = cleanup_tmp_files(max_age_hours=24)
    deleted_actions = await confirm_store.cleanup_expired()

    await callback.message.answer(
        f"✅ Очистка завершена:\n"
        f"🗑️ Временных файлов: {deleted_files}\n"
        f"🗑️ Истёкших подтверждений: {deleted_actions}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "/health")
async def health_check(message: Message) -> None:
    """Simple health check for monitoring."""
    sheets_ok = (await sheets_client.test_connection()).get("ok", False)
    drive_ok = (await drive_client.test_connection()).get("ok", False)

    if sheets_ok and drive_ok:
        await message.answer("✅ OK")
    else:
        issues = []
        if not sheets_ok:
            issues.append("sheets")
        if not drive_ok:
            issues.append("drive")
        await message.answer(f"⚠️ DEGRADED: {', '.join(issues)}")
