"""Catalog and search handlers."""

from __future__ import annotations

import logging

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import cart_store
from ..keyboards import back_to_menu_kb, categories_kb, main_menu_kb, product_kb
from ..services import ProductService
from ..sheets import SheetsClient
from .common import format_product, format_product_card

logger = logging.getLogger(__name__)


class SearchState(StatesGroup):
    query = State()


def register_catalog_handlers(
    dp: Dispatcher,
    product_service: ProductService,
    sheets_client: SheetsClient,
) -> None:
    """Register catalog handlers."""

    @dp.message(F.text == "🗂 Каталог")
    async def text_catalog(m: Message):
        user_id = m.from_user.id

        # CRM: Log catalog view event
        await cart_store.log_crm_event(user_id, 'catalog_view', {
            'category': 'all',
            'source': 'text_button',
        })

        # CRM: Update lead stage to engaged
        try:
            await sheets_client.upsert_lead(user_id, stage='engaged')
        except Exception as e:
            logger.warning("lead_update_failed", extra={"user_id": user_id, "error": str(e)})

        products = product_service.get_available_products()
        if not products:
            await m.answer("Каталог пуст.", reply_markup=main_menu_kb())
            return

        product = products[0]
        caption = format_product_card(product)

        nav_row = [InlineKeyboardButton(text=f"📄 1/{len(products)}", callback_data="noop")]
        if len(products) > 1:
            nav_row.append(InlineKeyboardButton(text="След. ➡️", callback_data="catalog:1:all"))

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 В корзину", callback_data=f"add:{product['sku']}:1"
                    )
                ],
                nav_row,
                [
                    InlineKeyboardButton(text="🧺 Корзина", callback_data="cart:show"),
                    InlineKeyboardButton(text="📋 Меню", callback_data="menu"),
                ],
            ]
        )

        photo_url = product.get("photo_url", "")
        if photo_url:
            try:
                await m.answer_photo(photo_url, caption=caption, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await m.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await m.answer(caption, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query(F.data.startswith("catalog:"))
    async def catalog(cb: CallbackQuery):
        user_id = cb.from_user.id
        parts = cb.data.split(":")
        page = int(parts[1])
        category = parts[2] if len(parts) > 2 else "all"

        # CRM: Log catalog navigation
        await cart_store.log_crm_event(user_id, 'catalog_view', {
            'category': category,
            'page': page,
        })

        # CRM: Update lead stage to engaged
        try:
            await sheets_client.upsert_lead(user_id, stage='engaged')
        except Exception as e:
            logger.warning("lead_update_failed", extra={"user_id": user_id, "error": str(e)})

        products = product_service.filter_by_category(category)
        total_items = len(products)

        if not products:
            text = "Каталог пуст." if category == "all" else f"Нет товаров в категории «{category}»"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📋 Категории", callback_data="categories"),
                        InlineKeyboardButton(text="🏠 Меню", callback_data="menu"),
                    ],
                ]
            )
            await cb.message.edit_text(text, reply_markup=kb)
            await cb.answer()
            return

        # Show one product per page with photo
        page = max(0, min(page, total_items - 1))
        product = products[page]

        caption = format_product_card(product)

        # Navigation keyboard for visual catalog
        nav_row = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"catalog:{page - 1}:{category}")
            )
        nav_row.append(
            InlineKeyboardButton(text=f"📄 {page + 1}/{total_items}", callback_data="noop")
        )
        if page < total_items - 1:
            nav_row.append(
                InlineKeyboardButton(text="След. ➡️", callback_data=f"catalog:{page + 1}:{category}")
            )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 В корзину", callback_data=f"add:{product['sku']}:1"
                    ),
                    InlineKeyboardButton(text="➕ 5 шт.", callback_data=f"add:{product['sku']}:5"),
                ],
                nav_row,
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

        photo_url = product.get("photo_url", "")

        # Try to send/edit with photo
        if photo_url:
            try:
                # Delete old message and send new photo
                await cb.message.delete()
                await cb.message.answer_photo(
                    photo_url, caption=caption, parse_mode="HTML", reply_markup=kb
                )
            except Exception:
                # Fallback to text if photo fails
                try:
                    await cb.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
                except Exception:
                    await cb.message.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            try:
                await cb.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await cb.message.answer(caption, parse_mode="HTML", reply_markup=kb)

        await cb.answer()

    @dp.callback_query(F.data == "categories")
    async def show_categories(cb: CallbackQuery):
        categories = product_service.get_categories()
        if categories:
            text = "📋 <b>Выберите категорию:</b>"
        else:
            text = "📋 Категории не найдены. Добавьте теги в таблицу."
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=categories_kb(categories))
        await cb.answer()

    @dp.callback_query(F.data == "search:start")
    async def search_start(cb: CallbackQuery, state: FSMContext):
        await state.set_state(SearchState.query)
        await cb.message.answer("🔍 Введите название товара или SKU для поиска:")
        await cb.answer()

    @dp.message(SearchState.query)
    async def search_query(m: Message, state: FSMContext):
        user_id = m.from_user.id
        query = (m.text or "").strip().lower()

        # Валидация длины запроса
        if not query or len(query) > 200:
            await m.answer(
                "⚠️ Запрос должен быть от 1 до 200 символов.",
                reply_markup=back_to_menu_kb(),
            )
            await state.clear()
            return

        await state.clear()

        found = product_service.search(query)

        # CRM: Log search event
        await cart_store.log_crm_event(user_id, 'search', {
            'query': query,
            'results_count': len(found),
        })

        # CRM: Update lead stage to engaged
        try:
            await sheets_client.upsert_lead(user_id, stage='engaged')
        except Exception as e:
            logger.warning("lead_update_failed", extra={"user_id": user_id, "error": str(e)})

        from ..utils import escape_html

        escaped_query = escape_html(query)
        if found:
            text = f"🔍 <b>Результаты поиска:</b> «{escaped_query}»\n\n"
            text += "\n\n".join([format_product(p, compact=True) for p in found[:10]])
            if len(found) > 10:
                text += f"\n\n<i>...и ещё {len(found) - 10} товаров</i>"
        else:
            text = f"🔍 Ничего не найдено по запросу «{escaped_query}»"

        await m.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb())

    @dp.callback_query(F.data.startswith("product:"))
    async def product_detail(cb: CallbackQuery):
        """Show detailed product view with photo."""
        user_id = cb.from_user.id
        sku = cb.data.split(":")[1]
        product = product_service.get_product(sku)

        if not product:
            await cb.answer("Товар не найден")
            return

        # CRM: Log product view event
        await cart_store.log_crm_event(user_id, 'product_view', {
            'sku': sku,
            'name': product.get('name', ''),
            'price': product.get('price_rub', 0),
        })

        # CRM: Update lead stage to engaged
        try:
            await sheets_client.upsert_lead(user_id, stage='engaged')
        except Exception as e:
            logger.warning("lead_update_failed", extra={"user_id": user_id, "error": str(e)})

        text = format_product(product, compact=False)

        if product.get("photo_url"):
            try:
                await cb.message.answer_photo(
                    product["photo_url"],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=product_kb(sku),
                )
            except Exception:
                await cb.message.answer(text, parse_mode="HTML", reply_markup=product_kb(sku))
        else:
            await cb.message.answer(text, parse_mode="HTML", reply_markup=product_kb(sku))
        await cb.answer()
