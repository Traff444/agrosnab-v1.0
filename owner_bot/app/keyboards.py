"""Telegram keyboard builders."""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models import Product


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Приход товара"), KeyboardButton(text="📊 CRM")],
            [KeyboardButton(text="🔍 Найти товар"), KeyboardButton(text="📋 Заказы сегодня")],
            [KeyboardButton(text="🔧 Статус")],
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
    """Actions for a product card."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Приход", callback_data=f"product_intake_{product.row_number}"
                ),
                InlineKeyboardButton(
                    text="✏️ Редактировать", callback_data=f"product_edit_{product.row_number}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📷 Фото", callback_data=f"product_photo_{product.row_number}"
                ),
                InlineKeyboardButton(
                    text="🗑️ Деактивировать"
                    if product.active
                    else "✅ Активировать",
                    callback_data=f"product_toggle_{product.row_number}",
                ),
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
