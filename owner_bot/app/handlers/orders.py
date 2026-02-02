"""Orders summary handlers."""

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import get_settings
from app.keyboards import main_menu_keyboard

router = Router()


@router.message(F.text == "📋 Заказы сегодня")
async def show_orders_today(message: Message, state: FSMContext) -> None:
    """Show today's orders summary."""
    await state.clear()  # Clear FSM state to avoid conflicts with intake flow
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).date()

    # TODO: Implement orders fetching from Sheets when orders sheet is defined
    # For now, show placeholder

    await message.answer(
        f"📋 **Заказы за {today.strftime('%d.%m.%Y')}**\n\n"
        "🚧 Функция в разработке.\n\n"
        "Для работы с заказами необходимо:\n"
        "1. Определить структуру листа «Заказы»\n"
        "2. Настроить колонки с датой и статусом\n\n"
        "Обратитесь к разработчику для настройки.",
        reply_markup=main_menu_keyboard(),
    )


# Placeholder for future implementation
async def _fetch_orders_today():
    """Fetch orders from Google Sheets."""
    # This will be implemented when orders sheet structure is defined
    # Expected columns: OrderID, Date, Customer, Total, Status, Items
    pass


def _format_orders_summary(orders: list, total: float) -> str:
    """Format orders list as summary message."""
    if not orders:
        return "📭 Заказов за сегодня нет."

    lines = [f"📋 **Заказы: {len(orders)}**\n"]

    for order in orders[:10]:  # Limit to 10
        lines.append(
            f"• #{order.get('id', '?')} — {order.get('customer', 'Покупатель')} — "
            f"{order.get('total', 0):.2f} ₽"
        )

    if len(orders) > 10:
        lines.append(f"\n... и ещё {len(orders) - 10}")

    lines.append(f"\n💰 **Итого:** {total:.2f} ₽")

    return "\n".join(lines)
