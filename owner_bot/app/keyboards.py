"""Telegram keyboard builders."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Product


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Приход товара"), KeyboardButton(text="📊 Склад")],
            [KeyboardButton(text="🔍 Найти товар"), KeyboardButton(text="📋 Заказы сегодня")],
            [KeyboardButton(text="📊 CRM"), KeyboardButton(text="🔧 Статус")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Cancel action keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def confirm_cancel_keyboard() -> InlineKeyboardMarkup:
    """Inline confirm/cancel keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ]
        ]
    )


def photo_decision_keyboard(has_photo: bool) -> InlineKeyboardMarkup:
    """Photo decision keyboard for existing products."""
    if has_photo:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📷 Заменить фото", callback_data="photo_replace"),
                    InlineKeyboardButton(text="⏭️ Оставить текущее", callback_data="photo_keep"),
                ],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 Добавить фото", callback_data="photo_add"),
                InlineKeyboardButton(text="⏭️ Без фото", callback_data="photo_skip"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ]
    )


def photo_quality_keyboard(status: str) -> InlineKeyboardMarkup:
    """Photo quality review keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Использовать", callback_data="photo_accept"),
            InlineKeyboardButton(text="🔄 Улучшить", callback_data="photo_enhance"),
        ],
        [
            InlineKeyboardButton(text="📷 Переснять", callback_data="photo_retake"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_match_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    """Keyboard for selecting from matched products."""
    builder = InlineKeyboardBuilder()

    for product in products[:5]:
        label = f"{product.name[:30]} | {product.sku} | ₽{product.price:.0f}"
        builder.button(text=label, callback_data=f"match_{product.row_number}")

    builder.button(text="➕ Создать новый", callback_data="match_new")
    builder.button(text="❌ Отмена", callback_data="cancel")

    builder.adjust(1)
    return builder.as_markup()


def product_actions_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Actions for a product card (updated layout per plan)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Приход", callback_data=f"product_intake_{product.row_number}"
                ),
                InlineKeyboardButton(
                    text="➖ Списать", callback_data=f"product_writeoff_{product.row_number}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧮 Корректировка", callback_data=f"product_correction_{product.row_number}"
                ),
                InlineKeyboardButton(
                    text="📷 Фото", callback_data=f"product_photo_{product.row_number}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Архив", callback_data=f"product_archive_{product.row_number}"
                ),
                InlineKeyboardButton(
                    text="⋯ Ещё", callback_data=f"product_more_{product.row_number}"
                ),
            ],
        ]
    )


def product_more_keyboard(product: Product) -> InlineKeyboardMarkup:
    """Additional actions menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать", callback_data=f"product_edit_{product.row_number}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад", callback_data=f"product_back_{product.row_number}"
                ),
            ],
        ]
    )


def writeoff_reason_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting writeoff reason."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Порча", callback_data="writeoff_reason_порча"),
                InlineKeyboardButton(text="🎁 Подарок", callback_data="writeoff_reason_подарок"),
            ],
            [
                InlineKeyboardButton(text="🔄 Пересорт", callback_data="writeoff_reason_пересорт"),
                InlineKeyboardButton(text="📝 Другое", callback_data="writeoff_reason_другое"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


def correction_reason_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting correction reason."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Инвентаризация", callback_data="correction_reason_инвентаризация"
                ),
            ],
            [
                InlineKeyboardButton(text="🔄 Пересорт", callback_data="correction_reason_пересорт"),
                InlineKeyboardButton(
                    text="⚠️ Ошибки учёта", callback_data="correction_reason_ошибки_учёта"
                ),
            ],
            [
                InlineKeyboardButton(text="📝 Другое", callback_data="correction_reason_другое"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


def archive_menu_keyboard(row_number: int) -> InlineKeyboardMarkup:
    """Archive action selection menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ Архивировать (убрать из каталога)",
                    callback_data=f"archive_simple_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧹 Обнулить остаток и архивировать",
                    callback_data=f"archive_zero_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


def over_stock_keyboard(row_number: int, available_stock: int) -> InlineKeyboardMarkup:
    """Keyboard shown when writeoff qty exceeds stock."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Списать остаток ({available_stock})",
                    callback_data=f"writeoff_all_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧮 Перейти в корректировку",
                    callback_data=f"product_correction_{row_number}",
                ),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ],
        ]
    )


def stock_operation_result_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after successful stock operation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ К товару", callback_data="back_to_product"),
                InlineKeyboardButton(text="🔎 Поиск", callback_data="start_search"),
            ],
        ]
    )


def retry_keyboard(action: str) -> InlineKeyboardMarkup:
    """Retry action keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Повторить", callback_data=f"retry_{action}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ]
        ]
    )


def confirmation_keyboard(action_id: str) -> InlineKeyboardMarkup:
    """Confirmation with action ID for dangerous operations."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, подтверждаю", callback_data=f"confirm_action_{action_id}"
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
            ]
        ]
    )


def pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
) -> InlineKeyboardMarkup:
    """Pagination keyboard."""
    buttons = []

    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"{prefix}_page_{current_page - 1}")
        )

    buttons.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop")
    )

    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"{prefix}_page_{current_page + 1}")
        )

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def stock_list_keyboard(
    products: list[Product],
    current_page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Stock list with pagination."""
    buttons = []

    for p in products:
        status = "✅" if p.active else "❌"
        label = f"{status} {p.name[:25]} ({p.stock} шт.)"
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"stock_select_{p.row_number}"
            )
        ])

    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"stock_page_{current_page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"stock_page_{current_page + 1}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="stock_close")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
