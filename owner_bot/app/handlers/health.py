"""Health check and status handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.cloudinary_client import cloudinary_client
from app.config import get_settings
from app.keyboards import main_menu_keyboard
from app.photo_enhance import cleanup_tmp_files
from app.security import confirm_store
from app.sheets import sheets_client

router = Router()

SHEETS_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}"
CLOUDINARY_URL = "https://console.cloudinary.com/console/c-{cloud_name}/media_library/folders/{folder}"


@router.message(F.text == "🔧 Статус")
async def show_status(message: Message, state: FSMContext) -> None:
    """Show system status and health checks."""
    await state.clear()  # Clear FSM state to avoid conflicts with intake flow
    await message.answer("🔍 Проверяю подключения...")

    settings = get_settings()

    sheets_status = await sheets_client.test_connection()
    cloud_status = await cloudinary_client.test_connection()

    lines = ["🔧 *Статус системы*\n"]

    # Google Sheets status
    if sheets_status.get("ok"):
        title = sheets_status.get("spreadsheet_title", "N/A")
        lines.append(f"✅ *Google Sheets*")
        lines.append(f"   Таблица: {title}")
        sheets = sheets_status.get("sheets", [])
        if sheets:
            lines.append(f"   Листы: {', '.join(sheets)}")
        cols = sheets_status.get("columns_found", [])
        if cols:
            lines.append(f"   Колонки: {len(cols)} найдено")
        sheet_link = SHEETS_URL.format(sheet_id=settings.google_sheets_id)
        lines.append(f"   📎 [Открыть таблицу]({sheet_link})")
    else:
        lines.append("❌ *Google Sheets*")
        error = sheets_status.get("error", "Неизвестная ошибка")
        lines.append(f"   Ошибка: {error}")
        missing = sheets_status.get("missing_columns", [])
        if missing:
            lines.append(f"   Отсутствуют колонки: {', '.join(missing)}")

    lines.append("")

    # Cloudinary status
    if cloud_status.get("ok"):
        cloud_name = cloud_status.get("cloud_name", "N/A")
        folder = cloud_status.get("folder", "mahorka_products")
        lines.append("✅ *Cloudinary*")
        lines.append(f"   Облако: {cloud_name}")
        lines.append(f"   Папка: {folder}")
        cloud_link = CLOUDINARY_URL.format(cloud_name=cloud_name, folder=folder)
        lines.append(f"   📎 [Открыть медиатеку]({cloud_link})")
    else:
        lines.append("❌ *Cloudinary*")
        lines.append(f"   Ошибка: {cloud_status.get('error', 'Неизвестная ошибка')}")

    lines.append("")
    lines.append("🧹 Для очистки временных файлов: /cleanup")

    await message.answer(
        "\n".join(lines),
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


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
    cloud_ok = (await cloudinary_client.test_connection()).get("ok", False)

    if sheets_ok and cloud_ok:
        await message.answer("✅ OK")
    else:
        issues = []
        if not sheets_ok:
            issues.append("sheets")
        if not cloud_ok:
            issues.append("cloudinary")
        await message.answer(f"⚠️ DEGRADED: {', '.join(issues)}")
