from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from . import cart_store
from .ai_manager import run_ai
from .config import Settings
from .invoice import generate_invoice_pdf
from .keyboards import (
    back_to_menu_kb,
    cart_kb,
    cart_with_items_kb,
    catalog_page_kb,
    categories_kb,
    main_menu_kb,
    persistent_menu,
    product_kb,
)
from .sheets import SheetsClient
from .utils import make_order_id

PAGE_SIZE = 5


class CheckoutState(StatesGroup):
    phone = State()
    delivery = State()


class SearchState(StatesGroup):
    query = State()


def format_product(p: dict[str, Any], compact: bool = False) -> str:
    """Format product for display. compact=True for catalog list, False for detail."""
    stock = p["stock"]
    stock_emoji = "✅" if stock > 5 else ("⚠️" if stock > 0 else "❌")

    if compact:
        # Short format for catalog list
        return (
            f"🏷 *{p['name']}*\n💰 {p['price_rub']:,} ₽ • {stock_emoji} {stock} шт.\n📦 `{p['sku']}`"
        )
    else:
        # Full format with description
        desc = p.get("desc_short", "")
        tags = p.get("tags", "")
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"🏷 *{p['name']}*",
            "",
            f"💰 *Цена:* {p['price_rub']:,} ₽",
            f"{stock_emoji} *В наличии:* {stock} шт.",
            f"📦 *Артикул:* `{p['sku']}`",
        ]
        if desc:
            lines.append(f"\n📝 {desc}")
        if tags:
            lines.append(f"\n🔖 {tags}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


async def send_product_card(bot: Bot, chat_id: int, p: dict[str, Any]) -> None:
    text = format_product(p)
    if p.get("photo_url"):
        await bot.send_photo(
            chat_id,
            p["photo_url"],
            caption=text,
            parse_mode="Markdown",
            reply_markup=product_kb(p["sku"]),
        )
    else:
        await bot.send_message(
            chat_id, text, parse_mode="Markdown", reply_markup=product_kb(p["sku"])
        )


async def calc_cart(products_by_sku: dict[str, dict[str, Any]], cart_items):
    lines = []
    total = 0
    for sku, qty in cart_items:
        p = products_by_sku.get(sku)
        if not p:
            continue
        line_sum = qty * p["price_rub"]
        total += line_sum
        lines.append(f"- {p['name']} ({sku}) × {qty} = {line_sum} ₽")
    return lines, total


async def main():
    cfg = Settings()

    bot = Bot(token=cfg.telegram_bot_token)
    dp = Dispatcher()

    sheets = SheetsClient(cfg.sheet_id(), cfg.google_service_account_json_path)

    await cart_store.init_db()

    @dp.message(CommandStart())
    async def start(m: Message):
        # AI режим включён по умолчанию
        await cart_store.set_ai_mode(m.from_user.id, True)
        # Показываем постоянное меню снизу
        await m.answer(
            "👋 Добро пожаловать в наш магазин!\n\n"
            "🤖 AI-менеджер уже активен — просто напишите что вам нужно!\n"
            "Например: «что есть?» или «добавь 5 золотой»\n\n"
            "Или используйте кнопки снизу:",
            reply_markup=persistent_menu(),
        )
        # Показываем inline меню с дополнительными опциями
        await m.answer(
            "👇 Дополнительные действия:",
            reply_markup=main_menu_kb(),
        )

    # Обработчики текстовых кнопок (постоянное меню снизу)
    @dp.message(F.text == "🗂 Каталог")
    async def text_catalog(m: Message):
        # AI mode stays on
        products = sheets.get_products()
        products = [p for p in products if p["stock"] > 0 and p["price_rub"] > 0]
        if not products:
            await m.answer("Каталог пуст.", reply_markup=main_menu_kb())
            return
        product = products[0]
        stock_emoji = "✅" if product["stock"] > 5 else ("⚠️" if product["stock"] > 0 else "❌")
        caption = (
            f"🏷 *{product['name']}*\n\n"
            f"💰 *Цена:* {product['price_rub']:,} ₽\n"
            f"{stock_emoji} *В наличии:* {product['stock']} шт.\n"
            f"📦 *Артикул:* `{product['sku']}`"
        )
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
                await m.answer_photo(
                    photo_url, caption=caption, parse_mode="Markdown", reply_markup=kb
                )
            except Exception:
                await m.answer(caption, parse_mode="Markdown", reply_markup=kb)
        else:
            await m.answer(caption, parse_mode="Markdown", reply_markup=kb)

    @dp.message(F.text == "🧺 Корзина")
    async def text_cart(m: Message):
        # AI mode stays on
        products = sheets.get_products()
        products_by_sku = {p["sku"]: p for p in products}
        cart_items = await cart_store.get_cart(m.from_user.id)
        settings = sheets.get_settings()
        min_sum = int(float(settings.get("Мин. сумма заказа", 5000)))
        if not cart_items:
            await m.answer(
                "🧺 *Корзина*\n\nПока пусто. Добавьте товары из каталога!",
                parse_mode="Markdown",
                reply_markup=cart_kb(),
            )
        else:
            lines = []
            total = 0
            items_for_kb = []
            for sku, qty in cart_items:
                p = products_by_sku.get(sku)
                if not p:
                    continue
                line_sum = qty * p["price_rub"]
                total += line_sum
                lines.append(f"• *{p['name']}*\n  {qty} × {p['price_rub']:,} ₽ = *{line_sum:,} ₽*")
                items_for_kb.append((sku, qty, p["name"]))
            text = "🧺 *Корзина*\n\n" + "\n\n".join(lines)
            text += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n💰 *Итого: {total:,} ₽*"
            if total < min_sum:
                text += f"\n⚠️ Минималка: {min_sum:,} ₽"
            await m.answer(
                text, parse_mode="Markdown", reply_markup=cart_with_items_kb(items_for_kb)
            )

    @dp.message(F.text == "🤖 AI Менеджер")
    async def text_ai(m: Message):
        await cart_store.set_ai_mode(m.from_user.id, True)
        await m.answer(
            "🤖 *AI Менеджер включён!*\n\n"
            "Напишите что вам нужно, например:\n"
            "• «Что у вас есть?»\n"
            "• «Покажи махорку»\n"
            "• «Добавь PRD-001, 5 штук»",
            parse_mode="Markdown",
        )

    @dp.message(F.text == "📋 Меню")
    async def text_menu(m: Message):
        # AI mode stays on
        await m.answer(
            "📋 *Главное меню*\n\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

    @dp.callback_query(F.data == "menu")
    async def menu(cb: CallbackQuery):
        # AI mode stays on
        try:
            await cb.message.edit_text(
                "📋 *Меню*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            await cb.message.answer(
                "📋 *Меню*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(),
            )
        await cb.answer()

    @dp.callback_query(F.data.startswith("catalog:"))
    async def catalog(cb: CallbackQuery):
        parts = cb.data.split(":")
        page = int(parts[1])
        category = parts[2] if len(parts) > 2 else "all"

        products = sheets.get_products()
        # filter only in-stock for catalog view
        products = [p for p in products if p["stock"] > 0 and p["price_rub"] > 0]

        # Apply category filter
        if category != "all":
            products = [p for p in products if category.lower() in p.get("tags", "").lower()]

        total_items = len(products)

        if not products:
            text = "Каталог пуст." if category == "all" else f"Нет товаров в категории «{category}»"
            await cb.message.edit_text(
                text, reply_markup=catalog_page_kb(0, False, False, category, 0)
            )
            await cb.answer()
            return

        # Show one product per page with photo
        page = max(0, min(page, total_items - 1))
        product = products[page]

        # Format product card
        stock_emoji = "✅" if product["stock"] > 5 else ("⚠️" if product["stock"] > 0 else "❌")
        caption = (
            f"🏷 *{product['name']}*\n\n"
            f"💰 *Цена:* {product['price_rub']:,} ₽\n"
            f"{stock_emoji} *В наличии:* {product['stock']} шт.\n"
            f"📦 *Артикул:* `{product['sku']}`"
        )

        desc = product.get("desc_short", "")
        if desc:
            caption += f"\n\n📝 _{desc}_"

        tags = product.get("tags", "")
        if tags:
            caption += f"\n\n🔖 {tags}"

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
                    photo_url, caption=caption, parse_mode="Markdown", reply_markup=kb
                )
            except Exception:
                # Fallback to text if photo fails
                try:
                    await cb.message.edit_text(caption, parse_mode="Markdown", reply_markup=kb)
                except Exception:
                    await cb.message.answer(caption, parse_mode="Markdown", reply_markup=kb)
        else:
            try:
                await cb.message.edit_text(caption, parse_mode="Markdown", reply_markup=kb)
            except Exception:
                await cb.message.answer(caption, parse_mode="Markdown", reply_markup=kb)

        await cb.answer()

    @dp.callback_query(F.data == "categories")
    async def show_categories(cb: CallbackQuery):
        categories = sheets.get_categories()
        if categories:
            text = "📋 *Выберите категорию:*"
        else:
            text = "📋 Категории не найдены. Добавьте теги в таблицу."
        await cb.message.edit_text(
            text, parse_mode="Markdown", reply_markup=categories_kb(categories)
        )
        await cb.answer()

    @dp.callback_query(F.data == "search:start")
    async def search_start(cb: CallbackQuery, state: FSMContext):
        await state.set_state(SearchState.query)
        await cb.message.answer("🔍 Введите название товара или SKU для поиска:")
        await cb.answer()

    @dp.message(SearchState.query)
    async def search_query(m: Message, state: FSMContext):
        query = (m.text or "").strip().lower()
        await state.clear()

        products = sheets.get_products()
        found = []
        for p in products:
            hay = (
                p["name"] + " " + p.get("tags", "") + " " + p.get("desc_short", "") + " " + p["sku"]
            ).lower()
            if query in hay:
                found.append(p)

        if found:
            text = f"🔍 *Результаты поиска:* «{query}»\n\n" + "\n\n".join(
                [format_product(p, compact=True) for p in found[:10]]
            )
            if len(found) > 10:
                text += f"\n\n_...и ещё {len(found) - 10} товаров_"
        else:
            text = f"🔍 Ничего не найдено по запросу «{query}»"

        await m.answer(text, parse_mode="Markdown", reply_markup=back_to_menu_kb())

    @dp.callback_query(F.data.startswith("add:"))
    async def add(cb: CallbackQuery):
        _, sku, qty_s = cb.data.split(":")
        qty = int(qty_s)

        # Get product name for better feedback
        products = sheets.get_products()
        product = next((p for p in products if p["sku"] == sku), None)
        product_name = product["name"] if product else sku

        await cart_store.add_to_cart(cb.from_user.id, sku, qty)

        # Show popup with cart info
        cart_items = await cart_store.get_cart(cb.from_user.id)
        total_items = sum(q for _, q in cart_items)

        await cb.answer(
            f"✅ {product_name} × {qty} добавлено!\n🧺 В корзине: {total_items} шт.",
            show_alert=True,
        )

    @dp.callback_query(F.data.startswith("product:"))
    async def product_detail(cb: CallbackQuery):
        """Show detailed product view with photo."""
        sku = cb.data.split(":")[1]
        products = sheets.get_products()
        product = next((p for p in products if p["sku"] == sku), None)

        if not product:
            await cb.answer("Товар не найден")
            return

        text = format_product(product, compact=False)

        if product.get("photo_url"):
            try:
                await cb.message.answer_photo(
                    product["photo_url"],
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=product_kb(sku),
                )
            except Exception:
                await cb.message.answer(text, parse_mode="Markdown", reply_markup=product_kb(sku))
        else:
            await cb.message.answer(text, parse_mode="Markdown", reply_markup=product_kb(sku))
        await cb.answer()

    @dp.callback_query(F.data == "cart:show")
    async def show_cart(cb: CallbackQuery):
        products = sheets.get_products()
        products_by_sku = {p["sku"]: p for p in products}
        cart_items = await cart_store.get_cart(cb.from_user.id)

        settings = sheets.get_settings()
        min_sum = int(float(settings.get("Мин. сумма заказа", 5000)))

        if not cart_items:
            text = "🧺 *Корзина*\n\nПока пусто. Добавьте товары из каталога!"
            kb = cart_kb()
        else:
            # Build cart display with items
            lines = []
            total = 0
            items_for_kb = []
            for sku, qty in cart_items:
                p = products_by_sku.get(sku)
                if not p:
                    continue
                line_sum = qty * p["price_rub"]
                total += line_sum
                lines.append(f"• *{p['name']}*\n  {qty} × {p['price_rub']:,} ₽ = *{line_sum:,} ₽*")
                items_for_kb.append((sku, qty, p["name"]))

            text = "🧺 *Корзина*\n\n" + "\n\n".join(lines)
            text += f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n💰 *Итого: {total:,} ₽*"

            if total < min_sum:
                text += f"\n⚠️ Минималка: {min_sum:,} ₽"

            kb = cart_with_items_kb(items_for_kb)

        # Try to edit, if fails (photo message) - delete and send new
        try:
            await cb.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            try:
                await cb.message.delete()
            except Exception:
                pass
            await cb.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        await cb.answer()

    @dp.callback_query(F.data.startswith("cart:inc:"))
    async def cart_inc(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        await cart_store.add_to_cart(cb.from_user.id, sku, 1)
        await show_cart(cb)

    @dp.callback_query(F.data.startswith("cart:dec:"))
    async def cart_dec(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        cart_items = await cart_store.get_cart(cb.from_user.id)
        current_qty = next((qty for s, qty in cart_items if s == sku), 0)
        if current_qty > 1:
            await cart_store.add_to_cart(cb.from_user.id, sku, -1)
        else:
            await cart_store.remove_from_cart(cb.from_user.id, sku)
        await show_cart(cb)

    @dp.callback_query(F.data.startswith("cart:remove:"))
    async def cart_remove(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        await cart_store.remove_from_cart(cb.from_user.id, sku)
        await show_cart(cb)

    @dp.callback_query(F.data == "cart:clear")
    async def clear(cb: CallbackQuery):
        await cart_store.clear_cart(cb.from_user.id)
        await show_cart(cb)

    @dp.callback_query(F.data == "checkout:start")
    async def checkout_start(cb: CallbackQuery, state: FSMContext):
        cart_items = await cart_store.get_cart(cb.from_user.id)
        if not cart_items:
            await cb.answer("Корзина пустая")
            return

        # min check
        products = sheets.get_products()
        products_by_sku = {p["sku"]: p for p in products}
        _, total = await calc_cart(products_by_sku, cart_items)

        settings = sheets.get_settings()
        min_sum = int(float(settings.get("Мин. сумма заказа", 5000)))
        if total < min_sum:
            await cb.answer(f"Минималка {min_sum} ₽")
            return

        await state.set_state(CheckoutState.phone)
        await cb.message.answer("Введите номер телефона (пример: +79990000000):")
        await cb.answer()

    @dp.message(CheckoutState.phone)
    async def checkout_phone(m: Message, state: FSMContext):
        phone = (m.text or "").strip()
        await state.update_data(phone=phone)
        await state.set_state(CheckoutState.delivery)
        await m.answer(
            "Введите доставку/город/ПВЗ (пока текстом, например: «СДЭК, Москва, ПВЗ Тверская 7»):"
        )

    @dp.message(CheckoutState.delivery)
    async def checkout_delivery(m: Message, state: FSMContext):
        data = await state.get_data()
        phone = data.get("phone", "")
        delivery = (m.text or "").strip()

        products = sheets.get_products()
        products_by_sku = {p["sku"]: p for p in products}
        cart_items = await cart_store.get_cart(m.from_user.id)
        lines, total = await calc_cart(products_by_sku, cart_items)

        # make invoice
        order_id = make_order_id("ORD")
        invoice_no = order_id
        invoice_date = datetime.now().strftime("%Y-%m-%d")

        seller = sheets.get_settings()

        items_for_pdf = []
        spisanie_rows = []
        for sku, qty in cart_items:
            p = products_by_sku.get(sku)
            if not p:
                continue
            items_for_pdf.append((sku, p["name"], qty, int(p["price_rub"])))
            spisanie_rows.append(
                [
                    invoice_date,
                    sku,
                    qty,
                    "",
                    "Тест",
                    invoice_no,
                    order_id,
                    "Авто-списание после счета",
                ]
            )

        out_pdf = f"/app/data/invoices/{invoice_no}.pdf"
        generate_invoice_pdf(
            out_pdf,
            invoice_no=invoice_no,
            invoice_date=invoice_date,
            seller=seller,
            buyer_phone=phone,
            delivery=delivery,
            items=items_for_pdf,
        )

        # write order to sheet
        order_row = [
            order_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(m.from_user.id),
            phone,
            "Счет выставлен",
            total,
            "СДЭК",
            delivery,
            "; ".join([f"{sku}:{qty}" for sku, qty in cart_items]),
            f"{invoice_no}.pdf",
        ]
        sheets.append_order(order_row)

        # optional spisanie
        if Settings().auto_write_spisanie:
            sheets.append_spisanie_rows(spisanie_rows)
            # Also update stock in Склад sheet
            sheets.decrease_stock([(sku, qty) for sku, qty in cart_items])

        await m.answer("✅ Счет сформирован. Отправляю PDF…")
        await m.answer_document(FSInputFile(out_pdf), caption=f"Счет № {invoice_no}")

        await cart_store.clear_cart(m.from_user.id)
        await state.clear()

    @dp.callback_query(F.data == "info:terms")
    async def terms(cb: CallbackQuery):
        settings = sheets.get_settings()
        min_sum = settings.get("Мин. сумма заказа", 5000)
        t1 = settings.get("Условие 1", "")
        text = f"📌 **Условия**\n\nМинимальная сумма заказа: {min_sum} ₽\n{t1}"
        await cb.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_menu_kb())
        await cb.answer()

    @dp.callback_query(F.data == "mode:ai")
    async def ai_mode(cb: CallbackQuery):
        await cart_store.set_ai_mode(cb.from_user.id, True)
        await cb.message.answer(
            "🤖 Режим ИИ-менеджера включён. Напишите, что вам нужно (например: «нужен товар 1, 5 штук»)."
        )
        await cb.answer()

    @dp.message()
    async def any_text(m: Message):
        print(f"[DEBUG] any_text called, text={m.text}")
        # если пользователь не в AI режиме — не перехватываем
        ai_mode = await cart_store.get_ai_mode(m.from_user.id)
        print(f"[DEBUG] ai_mode={ai_mode}")
        if not ai_mode:
            return

        cfg2 = Settings()
        print(f"[DEBUG] openai_api_key exists: {bool(cfg2.openai_api_key)}")
        if not cfg2.openai_api_key:
            await m.answer(
                "ИИ-режим отключен: не задан OPENAI_API_KEY. Можно пользоваться каталогом кнопками."
            )
            return

        print("[DEBUG] Calling run_ai...")

        # tool implementations
        async def tool_search(args):
            q = str(args.get("query", "")).strip().lower()
            products = sheets.get_products()
            found = []
            for p in products:
                hay = (p["name"] + " " + p.get("tags", "") + " " + p.get("desc_short", "")).lower()
                if q and q in hay:
                    found.append({k: p[k] for k in ("sku", "name", "price_rub", "stock")})
            return {"results": found[:10]}

        async def tool_add(args):
            sku = str(args.get("sku", "")).strip()
            qty = int(args.get("qty", 1))
            print(f"[CART DEBUG] Adding to cart: user_id={m.from_user.id}, sku={sku}, qty={qty}")
            await cart_store.add_to_cart(m.from_user.id, sku, qty)
            print("[CART DEBUG] add_to_cart completed")
            return {"ok": True, "added": {"sku": sku, "qty": qty}}

        async def tool_cart(args):
            cart_items = await cart_store.get_cart(m.from_user.id)
            products = sheets.get_products()
            products_by_sku = {p["sku"]: p for p in products}
            lines, total = await calc_cart(products_by_sku, cart_items)
            return {"lines": lines, "total": total}

        async def tool_checkout_hint(args):
            return {
                "hint": "Нажмите «Корзина» → «Оформить». Понадобится телефон и строка доставки (город/ПВЗ)."
            }

        async def tool_list_all(args):
            products = sheets.get_products()
            result = []
            for p in products:
                if p["stock"] > 0 and p["price_rub"] > 0:
                    result.append(
                        {
                            "sku": p["sku"],
                            "name": p["name"],
                            "price_rub": p["price_rub"],
                            "stock": p["stock"],
                            "tags": p.get("tags", ""),
                        }
                    )
            return {"products": result, "total_count": len(result)}

        tool_impl = {
            "search_products": tool_search,
            "add_to_cart": tool_add,
            "show_cart": tool_cart,
            "checkout_hint": tool_checkout_hint,
            "list_all_products": tool_list_all,
        }

        # Получаем историю диалога
        history = await cart_store.get_chat_history(m.from_user.id)

        # Сохраняем сообщение пользователя в историю
        await cart_store.add_chat_message(m.from_user.id, "user", m.text or "")

        out = await run_ai(
            api_key=cfg2.openai_api_key,
            model=cfg2.openai_model,
            user_text=m.text or "",
            tool_impl=tool_impl,
            history=history,
        )

        response_text = out.get("text", "")

        # Сохраняем ответ AI в историю
        if response_text:
            await cart_store.add_chat_message(m.from_user.id, "assistant", response_text)
            await m.answer(response_text, parse_mode="Markdown")

        # После ответа AI показываем кнопки для действий
        await m.answer("👇 Быстрые действия:", reply_markup=cart_kb())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
