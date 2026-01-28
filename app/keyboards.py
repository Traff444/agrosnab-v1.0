from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def persistent_menu() -> ReplyKeyboardMarkup:
    """Постоянное меню снизу экрана."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗂 Каталог"), KeyboardButton(text="🧺 Корзина")],
            [KeyboardButton(text="🤖 AI Менеджер"), KeyboardButton(text="📋 Меню")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗂 Каталог", callback_data="catalog:0:all"),
                InlineKeyboardButton(text="🧺 Корзина", callback_data="cart:show"),
            ],
            [
                InlineKeyboardButton(text="🔍 Поиск", callback_data="search:start"),
                InlineKeyboardButton(text="📋 Категории", callback_data="categories"),
            ],
            [
                InlineKeyboardButton(text="🤖 Менеджер", callback_data="mode:ai"),
                InlineKeyboardButton(text="📌 Условия", callback_data="info:terms"),
            ],
        ]
    )


def categories_kb(categories: list[str]) -> InlineKeyboardMarkup:
    """Generate keyboard with category buttons."""
    rows = []
    # Add "All" button
    rows.append([InlineKeyboardButton(text="📦 Все товары", callback_data="catalog:0:all")])
    # Add category buttons (2 per row)
    for i in range(0, len(categories), 2):
        row = [
            InlineKeyboardButton(
                text=f"🔖 {categories[i]}", callback_data=f"catalog:0:{categories[i]}"
            )
        ]
        if i + 1 < len(categories):
            row.append(
                InlineKeyboardButton(
                    text=f"🔖 {categories[i + 1]}", callback_data=f"catalog:0:{categories[i + 1]}"
                )
            )
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_page_kb(
    page: int, has_prev: bool, has_next: bool, category: str = "all", total_items: int = 0
) -> InlineKeyboardMarkup:
    row = []
    if has_prev:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"catalog:{page - 1}:{category}"))
    row.append(
        InlineKeyboardButton(text=f"📄 {page + 1} • {total_items} шт.", callback_data="noop")
    )
    if has_next:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"catalog:{page + 1}:{category}"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [
                InlineKeyboardButton(text="📋 Категории", callback_data="categories"),
                InlineKeyboardButton(text="🔍 Поиск", callback_data="search:start"),
            ],
            [
                InlineKeyboardButton(text="🧺 Корзина", callback_data="cart:show"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
            ],
        ]
    )


def product_kb(sku: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ В корзину (1)", callback_data=f"add:{sku}:1"),
                InlineKeyboardButton(text="➕➕ (5)", callback_data=f"add:{sku}:5"),
            ],
            [
                InlineKeyboardButton(text="🧺 Корзина", callback_data="cart:show"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog:0:all"),
            ],
        ]
    )


def cart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Оформить", callback_data="checkout:start"),
                InlineKeyboardButton(text="🧹 Очистить", callback_data="cart:clear"),
            ],
            [
                InlineKeyboardButton(text="🗂 Каталог", callback_data="catalog:0:all"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
            ],
        ]
    )


def cart_item_kb(sku: str, qty: int) -> list[InlineKeyboardButton]:
    """Return a row of buttons for one cart item: [➖] [qty] [➕] [🗑]"""
    return [
        InlineKeyboardButton(text="➖", callback_data=f"cart:dec:{sku}"),
        InlineKeyboardButton(text=f"{qty} шт.", callback_data="noop"),
        InlineKeyboardButton(text="➕", callback_data=f"cart:inc:{sku}"),
        InlineKeyboardButton(text="🗑", callback_data=f"cart:remove:{sku}"),
    ]


def cart_with_items_kb(items: list[tuple]) -> InlineKeyboardMarkup:
    """Cart keyboard with +/- controls for each item. items = [(sku, qty, name), ...]"""
    rows = []
    for sku, qty, name in items:
        # Item name row (truncated)
        display_name = (name[:20] + "…") if len(name) > 20 else name
        rows.append(
            [InlineKeyboardButton(text=f"📦 {display_name}", callback_data=f"product:{sku}")]
        )
        # Controls row
        rows.append(cart_item_kb(sku, qty))
    # Action buttons
    rows.append(
        [
            InlineKeyboardButton(text="✅ Оформить", callback_data="checkout:start"),
            InlineKeyboardButton(text="🧹 Очистить", callback_data="cart:clear"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="🗂 Каталог", callback_data="catalog:0:all"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Меню", callback_data="menu")]]
    )


# ---------------------------------------------------------------------------
# CDEK integration keyboards
# ---------------------------------------------------------------------------
PVZ_PER_PAGE = 8


def city_select_kb(cities: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """
    Keyboard for selecting a city from CDEK search results.
    cities: [(city_code, display_name), ...]
    """
    rows = []
    for city_code, display_name in cities[:10]:  # Max 10 cities
        # Truncate long names
        text = display_name if len(display_name) <= 35 else display_name[:32] + "..."
        rows.append(
            [InlineKeyboardButton(text=f"📍 {text}", callback_data=f"cdek:city:{city_code}")]
        )
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Ввести другой город", callback_data="cdek:city:retry"),
            InlineKeyboardButton(text="✉️ Ввести вручную", callback_data="cdek:manual"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pvz_select_kb(
    pvz_list: list[tuple[str, str]],
    city_code: int,
    page: int = 0,
) -> InlineKeyboardMarkup:
    """
    Keyboard for selecting a PVZ with pagination.
    pvz_list: [(pvz_code, display_address), ...]
    """
    total = len(pvz_list)
    start = page * PVZ_PER_PAGE
    end = start + PVZ_PER_PAGE
    page_items = pvz_list[start:end]

    rows = []
    for pvz_code, address in page_items:
        # Truncate address for button
        text = address if len(address) <= 40 else address[:37] + "..."
        rows.append(
            [InlineKeyboardButton(text=f"📍 {text}", callback_data=f"cdek:pvz:{pvz_code}")]
        )

    # Pagination row
    total_pages = (total + PVZ_PER_PAGE - 1) // PVZ_PER_PAGE
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"cdek:pvz_page:{city_code}:{page - 1}")
            )
        nav_row.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
        )
        if page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(text="➡️", callback_data=f"cdek:pvz_page:{city_code}:{page + 1}")
            )
        rows.append(nav_row)

    # Actions row
    rows.append(
        [
            InlineKeyboardButton(text="🔄 Другой город", callback_data="cdek:city:retry"),
            InlineKeyboardButton(text="✉️ Вручную", callback_data="cdek:manual"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения выбранного ПВЗ."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="cdek:confirm"),
                InlineKeyboardButton(text="🔄 Изменить", callback_data="cdek:city:retry"),
            ]
        ]
    )
