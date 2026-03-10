"""Cart and checkout handlers."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from .. import cart_store
from ..analytics import track
from ..config import Settings
from ..invoice import generate_invoice_pdf
from ..keyboards import (
    DELIVERY_TYPE_LABELS,
    delivery_type_kb,
    main_menu_kb,
    order_confirm_kb,
    use_saved_kb,
)
from ..services import CartService, ProductService
from ..sheets import SheetsClient, retry_async
from ..storage.cart import (
    generate_sequential_order_id,
    get_last_user_order,
    get_user_profile,
    save_user_order,
    save_user_profile,
)
from ..utils import escape_html, validate_fio, validate_phone

logger = logging.getLogger(__name__)


class CheckoutState(StatesGroup):
    phone = State()
    fio = State()
    delivery_type = State()
    address_input = State()  # СДЭК / Почта России
    courier_address = State()  # Курьер
    confirm = State()  # order confirmation before payment


OWNER_IDS = [int(x) for x in os.environ.get("OWNER_TELEGRAM_IDS", "").split(",") if x.strip()]
OWNER_BOT_TOKEN = os.environ.get("OWNER_BOT_TOKEN", "")


async def _notify_owners(
    order_id: str,
    buyer_name: str,
    buyer_phone: str,
    delivery_label: str,
    delivery_address: str,
    total: int,
    cart_items: list[tuple[str, int]],
    products_by_sku: dict,
) -> None:
    """Send new order notification to owners via the owner bot."""
    if not OWNER_BOT_TOKEN or not OWNER_IDS:
        logger.warning("Owner notification skipped: no OWNER_BOT_TOKEN or OWNER_TELEGRAM_IDS")
        return

    items_text = "\n".join(
        f"  - {products_by_sku.get(sku, {}).get('name', sku)} x{qty}"
        for sku, qty in cart_items
    )
    text = (
        f"🔔 <b>Новый заказ!</b>\n\n"
        f"📋 {order_id}\n"
        f"👤 {escape_html(buyer_name)}\n"
        f"📞 {buyer_phone}\n"
        f"💰 <b>{total:,} ₽</b>\n"
        f"📦 {delivery_label}\n"
        f"📍 {escape_html(delivery_address)}\n\n"
        f"<b>Товары:</b>\n{items_text}"
    )
    owner_bot = Bot(token=OWNER_BOT_TOKEN)
    try:
        for owner_id in OWNER_IDS:
            try:
                await owner_bot.send_message(owner_id, text, parse_mode="HTML")
            except Exception as e:
                logger.warning("Failed to notify owner %s: %s", owner_id, e)
    finally:
        await owner_bot.session.close()


def register_cart_handlers(
    dp: Dispatcher,
    product_service: ProductService,
    cart_service: CartService,
    sheets_client: SheetsClient,
) -> None:
    """Register cart and checkout handlers."""

    cfg = Settings()

    async def finalize_checkout(
        user_id: int,
        buyer_phone: str,
        buyer_name: str,
        delivery_type: str,
        delivery: str,
        message: Message,
        state: FSMContext,
    ) -> None:
        """Create invoice, write order to sheets, send PDF, clear cart and state."""
        # Parallel fetch: cart items and total calculation
        cart_items, (_, total, _) = await asyncio.gather(
            cart_store.get_cart(user_id),
            cart_service.calc_cart_for_checkout(user_id),
        )

        if not cart_items:
            await message.answer("Корзина пуста. Начните сначала.")
            await state.clear()
            return

        products_by_sku = product_service.get_products_by_sku()

        # Idempotent checkout: get or create session to avoid duplicate orders
        order_id, _ = await cart_store.get_or_create_checkout_session(
            user_id,
            cart_items,
            lambda: generate_sequential_order_id(user_id),
        )
        invoice_no = order_id
        invoice_date = datetime.now().strftime("%Y-%m-%d")

        seller = product_service.get_settings()

        items_for_pdf: list[tuple[str, str, int, int]] = []
        spisanie_rows: list[list] = []
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
                    buyer_name or buyer_phone,
                    invoice_no,
                    order_id,
                    "Авто-списание после счета",
                ]
            )

        out_pdf = f"/app/data/invoices/{invoice_no}.pdf"
        os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
        generate_invoice_pdf(
            out_pdf,
            invoice_no=invoice_no,
            invoice_date=invoice_date,
            seller=seller,
            buyer_phone=buyer_phone,
            buyer_name=buyer_name,
            delivery=delivery,
            items=items_for_pdf,
        )

        # write order to sheet (async with retry)
        delivery_type_label = DELIVERY_TYPE_LABELS.get(delivery_type, delivery_type)
        order_row = [
            order_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(user_id),
            buyer_phone,
            "Новый",
            total,
            delivery_type_label,
            delivery,
            "; ".join([f"{sku}:{qty}" for sku, qty in cart_items]),
            f"{invoice_no}.pdf",
            buyer_name,
        ]

        try:
            await retry_async(sheets_client.append_order, order_row)

            # optional spisanie (async with retry)
            if cfg.auto_write_spisanie:
                await retry_async(sheets_client.append_spisanie_rows, spisanie_rows)
                # Update stock in Склад sheet (now async with batch update)
                await retry_async(
                    sheets_client.decrease_stock, cart_items
                )
                # Invalidate cache after stock update
                product_service.invalidate_cache()

            # Mark checkout session as completed
            await cart_store.mark_checkout_complete(user_id, order_id)

            # CRM: Log order_created event
            await cart_store.log_crm_event(
                user_id,
                "order_created",
                {
                    "order_id": order_id,
                    "total": total,
                    "items_count": len(cart_items),
                    "delivery": delivery,
                },
            )

            track(user_id, "order_created", {
                "order_id": order_id,
                "total": total,
                "items_count": len(cart_items),
            })

            # CRM: Update lead stage to customer or repeat
            orders_count = await cart_store.get_user_orders_count(user_id)
            stage = "repeat" if orders_count >= 2 else "customer"

            # Calculate lifetime value
            events = await cart_store.get_user_events(user_id, event_types=["order_created"])
            lifetime_value = sum((e.get("payload") or {}).get("total", 0) for e in events)

            try:
                await sheets_client.upsert_lead(
                    user_id,
                    stage=stage,
                    phone=buyer_phone,
                    orders_count=orders_count,
                    lifetime_value=lifetime_value,
                    last_order_id=order_id,
                )
            except Exception as crm_error:
                logger.warning(
                    "lead_update_failed", extra={"user_id": user_id, "error": str(crm_error)}
                )

        except Exception as e:
            logger.error("Checkout failed for user %s: %s", user_id, e)
            await message.answer(
                "❌ Ошибка при сохранении заказа. Попробуйте ещё раз или свяжитесь с поддержкой."
            )
            await state.clear()
            return

        await message.answer("✅ Счет сформирован. Отправляю PDF…")
        await message.answer_document(FSInputFile(out_pdf), caption=f"Счет № {invoice_no}")

        # Thank you message with order details
        thank_you = (
            f"🎉 <b>Спасибо за заказ!</b>\n\n"
            f"📋 Номер заказа: <code>{order_id}</code>\n"
            f"👤 ФИО: {escape_html(buyer_name)}\n"
            f"💰 Сумма: <b>{total:,} ₽</b>\n"
            f"📦 Доставка: {delivery_type_label}\n\n"
            f"<b>Что дальше:</b>\n"
            f"1. Мы подготовим ваш заказ\n"
            f"2. Оплата при получении\n\n"
            f"❓ Вопросы? Напишите нам!"
        )
        await message.answer(thank_you, parse_mode="HTML", reply_markup=main_menu_kb())

        # Save user profile and order history for next order
        await save_user_profile(user_id, phone=buyer_phone, fio=buyer_name, last_address=delivery)
        await save_user_order(user_id, order_id, cart_items)

        # Notify owners about new order (via owner bot)
        await _notify_owners(
            order_id, buyer_name, buyer_phone,
            delivery_type_label, delivery, total, cart_items, products_by_sku,
        )

        await cart_store.clear_cart(user_id)
        await cart_store.cleanup_old_checkout_sessions(user_id)
        await state.clear()

    @dp.callback_query(F.data == "repeat_order")
    async def repeat_order(cb: CallbackQuery):
        user_id = cb.from_user.id
        last_items = await get_last_user_order(user_id)
        if not last_items:
            await cb.answer("У вас пока нет заказов", show_alert=True)
            return

        products_by_sku = product_service.get_products_by_sku()
        added = []
        skipped = []
        for sku, qty in last_items:
            p = products_by_sku.get(sku)
            if not p or int(p.get("stock", 0)) <= 0:
                skipped.append(sku)
                continue
            available = int(p.get("stock", 0))
            actual_qty = min(qty, available)
            await cart_store.add_to_cart(user_id, sku, actual_qty)
            added.append((p["name"], actual_qty))

        if not added:
            await cb.answer("Товары из прошлого заказа закончились", show_alert=True)
            return

        lines = [f"  {name} x{qty}" for name, qty in added]
        text = "🔄 <b>Добавлено из прошлого заказа:</b>\n" + "\n".join(lines)
        if skipped:
            text += f"\n\n⚠️ Нет в наличии: {len(skipped)} шт."
        text += "\n\nОткройте корзину для оформления."

        await cb.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
        await cb.answer()

    @dp.message(F.text.endswith("Корзина"))
    async def text_cart(m: Message):
        summary = await cart_service.get_cart_summary(m.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)
        await m.answer(text, parse_mode="HTML", reply_markup=kb)

    @dp.callback_query(F.data == "cart:show")
    async def show_cart(cb: CallbackQuery):
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)

        # Try to edit, if fails (photo message) - delete and send new
        try:
            await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest as e:
            logger.debug("Cannot edit message (likely photo): %s", e)
            try:
                await cb.message.delete()
            except TelegramBadRequest:
                pass
            await cb.message.answer(text, parse_mode="HTML", reply_markup=kb)
        await cb.answer()

    @dp.callback_query(F.data.startswith("add:"))
    async def add(cb: CallbackQuery):
        user_id = cb.from_user.id
        _, sku, qty_s = cb.data.split(":")
        qty = int(qty_s)

        success, message = await cart_service.add_to_cart(user_id, sku, qty)

        if success:
            # CRM: Log add_to_cart event
            await cart_store.log_crm_event(
                user_id,
                "add_to_cart",
                {
                    "sku": sku,
                    "qty": qty,
                },
            )

            track(user_id, "add_to_cart", {"product_id": sku, "qty": qty})

            # CRM: Update lead stage to cart
            try:
                await sheets_client.upsert_lead(user_id, stage="cart")
            except Exception as e:
                logger.warning("lead_update_failed", extra={"user_id": user_id, "error": str(e)})

        await cb.answer(message, show_alert=True)

    @dp.callback_query(F.data.startswith("cart:inc:"))
    async def cart_inc(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        success, _ = await cart_service.add_to_cart(cb.from_user.id, sku, 1)
        if success:
            # Refresh cart display
            summary = await cart_service.get_cart_summary(cb.from_user.id)
            text = cart_service.format_cart_text(summary)
            kb = cart_service.get_cart_keyboard(summary)
            try:
                await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except TelegramBadRequest as e:
                logger.debug("Cannot edit cart message: %s", e)
        await cb.answer()

    @dp.callback_query(F.data.startswith("cart:dec:"))
    async def cart_dec(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        cart_items = await cart_store.get_cart(cb.from_user.id)
        current_qty = next((qty for s, qty in cart_items if s == sku), 0)
        if current_qty > 1:
            await cart_store.add_to_cart(cb.from_user.id, sku, -1)
        else:
            await cart_store.remove_from_cart(cb.from_user.id, sku)

        # Refresh cart display
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)
        try:
            await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest as e:
            logger.debug("Cannot edit cart message: %s", e)
        await cb.answer()

    @dp.callback_query(F.data.startswith("cart:remove:"))
    async def cart_remove(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        track(cb.from_user.id, "remove_from_cart", {"product_id": sku})
        await cart_store.remove_from_cart(cb.from_user.id, sku)

        # Refresh cart display
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)
        try:
            await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest as e:
            logger.debug("Cannot edit cart message: %s", e)
        await cb.answer()

    @dp.callback_query(F.data == "cart:clear")
    async def clear(cb: CallbackQuery):
        await cart_store.clear_cart(cb.from_user.id)

        # Refresh cart display
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)
        try:
            await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except TelegramBadRequest as e:
            logger.debug("Cannot edit cart message: %s", e)
        await cb.answer()

    @dp.callback_query(F.data == "checkout:start")
    async def checkout_start(cb: CallbackQuery, state: FSMContext):
        user_id = cb.from_user.id
        # Parallel fetch: cart items, summary, saved profile
        cart_items, summary, profile = await asyncio.gather(
            cart_store.get_cart(user_id),
            cart_service.get_cart_summary(user_id),
            get_user_profile(user_id),
        )

        if not cart_items:
            await cb.answer("Корзина пустая")
            return

        # min check
        if summary.below_min:
            await cb.answer(f"Минималка {summary.min_sum} ₽")
            return

        track(user_id, "start_checkout", {"cart_total": summary.total, "items_count": len(cart_items)})

        await state.set_state(CheckoutState.phone)
        msg = "📞 Введите номер телефона (пример: +79990000000):"
        kb = None
        if profile.get("phone"):
            kb = use_saved_kb("phone", profile["phone"])
            msg += f"\n\nИли используйте сохранённый:"
        await cb.message.answer(msg, reply_markup=kb)
        await cb.answer()

    @dp.callback_query(F.data == "use_saved:phone")
    async def use_saved_phone(cb: CallbackQuery, state: FSMContext):
        user_id = cb.from_user.id
        profile = await get_user_profile(user_id)
        phone = profile.get("phone", "")
        if not phone:
            await cb.answer("Нет сохранённого номера")
            return
        await state.update_data(phone=phone)
        await _after_phone(user_id, phone, cb.message, state)
        await cb.answer()

    @dp.message(CheckoutState.phone)
    async def checkout_phone(m: Message, state: FSMContext):
        user_id = m.from_user.id
        raw_phone = (m.text or "").strip()
        is_valid, result = validate_phone(raw_phone)
        if not is_valid:
            await m.answer(f"❌ {result}\nПопробуйте ещё раз:")
            return
        await state.update_data(phone=result)
        await _after_phone(user_id, result, m, state)

    async def _after_phone(user_id: int, phone: str, message: Message, state: FSMContext):
        """Common logic after phone is set — CRM + ask FIO."""
        track(user_id, "enter_phone")

        await cart_store.log_crm_event(
            user_id, "checkout_started",
            {"phone": phone[:4] + "***" + phone[-2:] if len(phone) > 6 else "***"},
        )
        try:
            await sheets_client.upsert_lead(user_id, stage="checkout", phone=phone)
        except Exception as e:
            logger.warning("Failed to update lead %s: %s", user_id, e)

        profile = await get_user_profile(user_id)
        await state.set_state(CheckoutState.fio)
        msg = "👤 Введите ФИО получателя:"
        kb = None
        if profile.get("fio"):
            kb = use_saved_kb("fio", profile["fio"])
            msg += "\n\nИли используйте сохранённое:"
        await message.answer(msg, reply_markup=kb)

    @dp.callback_query(F.data == "use_saved:fio")
    async def use_saved_fio(cb: CallbackQuery, state: FSMContext):
        profile = await get_user_profile(cb.from_user.id)
        fio = profile.get("fio", "")
        if not fio:
            await cb.answer("Нет сохранённого ФИО")
            return
        await state.update_data(buyer_name=fio)
        await state.set_state(CheckoutState.delivery_type)
        await cb.message.answer("📦 Выберите способ доставки:", reply_markup=delivery_type_kb())
        await cb.answer()

    @dp.message(CheckoutState.fio)
    async def checkout_fio(m: Message, state: FSMContext):
        raw_fio = (m.text or "").strip()
        is_valid, result = validate_fio(raw_fio)
        if not is_valid:
            await m.answer(f"❌ {result}\nПопробуйте ещё раз:")
            return

        await state.update_data(buyer_name=result)
        await state.set_state(CheckoutState.delivery_type)
        await m.answer("📦 Выберите способ доставки:", reply_markup=delivery_type_kb())

    @dp.callback_query(F.data.startswith("delivery_type:"))
    async def delivery_type_selected(cb: CallbackQuery, state: FSMContext):
        dtype = cb.data.split(":")[1]
        await state.update_data(delivery_type=dtype)

        if dtype == "pickup":
            delivery = (
                "Самовывоз: Фуд Сити, м. Корниловская, "
                "вход 2/3, этаж 2, линия 22, пав. 60, «Табачный мир», 10:00-17:00"
            )
            data = await state.get_data()
            await cb.answer()
            await show_order_confirmation(
                cb.from_user.id,
                data.get("phone", ""),
                data.get("buyer_name", ""),
                dtype,
                delivery,
                cb.message,
                state,
            )
        elif dtype == "cdek_pvz":
            profile = await get_user_profile(cb.from_user.id)
            await state.set_state(CheckoutState.address_input)
            msg = (
                "📦 Доставка в ПВЗ СДЭК.\n"
                "Введите полный адрес с индексом\n"
                "(пример: 101000, г. Москва, ул. Мясницкая, д. 1):"
            )
            kb = None
            if profile.get("last_address"):
                kb = use_saved_kb("address", profile["last_address"][:40] + ("..." if len(profile["last_address"]) > 40 else ""))
                msg += "\n\nИли используйте сохранённый:"
            await cb.message.answer(msg, reply_markup=kb)
            await cb.answer()
        elif dtype == "pochta":
            profile = await get_user_profile(cb.from_user.id)
            await state.set_state(CheckoutState.address_input)
            msg = (
                "📮 Введите полный почтовый адрес с индексом\n"
                "(пример: 101000, г. Москва, ул. Мясницкая, д. 1, кв. 10):"
            )
            kb = None
            if profile.get("last_address"):
                kb = use_saved_kb("address", profile["last_address"][:40] + ("..." if len(profile["last_address"]) > 40 else ""))
                msg += "\n\nИли используйте сохранённый:"
            await cb.message.answer(msg, reply_markup=kb)
            await cb.answer()
        elif dtype == "courier":
            profile = await get_user_profile(cb.from_user.id)
            await state.set_state(CheckoutState.courier_address)
            msg = (
                "🚗 Курьерская доставка (Москва/МО, СПб/Ленобласть).\n"
                "Введите полный адрес доставки:"
            )
            kb = None
            if profile.get("last_address"):
                kb = use_saved_kb("address", profile["last_address"][:40] + ("..." if len(profile["last_address"]) > 40 else ""))
                msg += "\n\nИли используйте сохранённый:"
            await cb.message.answer(msg, reply_markup=kb)
            await cb.answer()
        else:
            await cb.answer("Неизвестный тип доставки", show_alert=True)

    @dp.callback_query(F.data == "use_saved:address")
    async def use_saved_address(cb: CallbackQuery, state: FSMContext):
        profile = await get_user_profile(cb.from_user.id)
        address = profile.get("last_address", "")
        if not address:
            await cb.answer("Нет сохранённого адреса")
            return
        data = await state.get_data()
        dtype = data.get("delivery_type", "pochta")
        label = DELIVERY_TYPE_LABELS.get(dtype, dtype).split(" ", 1)[-1]
        delivery = f"{label}: {address}"
        await cb.answer()
        await show_order_confirmation(
            cb.from_user.id,
            data.get("phone", ""),
            data.get("buyer_name", ""),
            dtype, delivery, cb.message, state,
        )

    @dp.message(CheckoutState.address_input)
    async def checkout_address_input(m: Message, state: FSMContext):
        address = (m.text or "").strip()
        if len(address) < 10:
            await m.answer("⚠️ Адрес слишком короткий. Укажите полный адрес с индексом:")
            return

        data = await state.get_data()
        dtype = data.get("delivery_type", "pochta")
        label = DELIVERY_TYPE_LABELS.get(dtype, dtype).split(" ", 1)[-1]
        delivery = f"{label}: {address}"
        await show_order_confirmation(
            m.from_user.id,
            data.get("phone", ""),
            data.get("buyer_name", ""),
            dtype, delivery, m, state,
        )

    @dp.message(CheckoutState.courier_address)
    async def checkout_courier_address(m: Message, state: FSMContext):
        address = (m.text or "").strip()
        if len(address) < 10:
            await m.answer("⚠️ Адрес слишком короткий. Укажите полный адрес:")
            return

        delivery = f"Курьер: {address}"
        data = await state.get_data()
        await show_order_confirmation(
            m.from_user.id,
            data.get("phone", ""),
            data.get("buyer_name", ""),
            data.get("delivery_type", "courier"),
            delivery,
            m,
            state,
        )

    async def show_order_confirmation(
        user_id: int,
        phone: str,
        buyer_name: str,
        delivery_type_val: str,
        delivery: str,
        message: Message,
        state: FSMContext,
    ) -> None:
        """Show order confirmation screen before finalizing."""
        lines, total, _ = await cart_service.calc_cart_for_checkout(user_id)

        if not lines:
            await message.answer("Корзина пуста. Начните сначала.")
            await state.clear()
            return

        items_text = "\n".join(lines)
        escaped_delivery = escape_html(delivery)
        delivery_type_label = DELIVERY_TYPE_LABELS.get(delivery_type_val, delivery_type_val)
        text = (
            "✅ <b>Подтверждение заказа</b>\n\n"
            f"📦 <b>Товары:</b>\n{items_text}\n\n"
            f"💰 <b>Итого: {total:,} ₽</b>\n\n"
            f"👤 ФИО: {escape_html(buyer_name)}\n"
            f"📞 Телефон: <code>{phone}</code>\n"
            f"📍 Доставка ({delivery_type_label}): {escaped_delivery}\n"
            f"💳 Оплата при получении\n\n"
            "Всё верно?"
        )

        await state.update_data(
            phone=phone, buyer_name=buyer_name, delivery_type=delivery_type_val, delivery=delivery
        )
        await state.set_state(CheckoutState.confirm)
        await message.answer(text, parse_mode="HTML", reply_markup=order_confirm_kb())

    @dp.callback_query(F.data == "checkout:final")
    async def checkout_final(cb: CallbackQuery, state: FSMContext):
        """Finalize order after user confirmation."""
        data = await state.get_data()
        phone = str(data.get("phone", "")).strip()
        buyer_name = str(data.get("buyer_name", "")).strip()
        delivery_type_val = str(data.get("delivery_type", "")).strip()
        delivery = str(data.get("delivery", "")).strip()

        if not phone or not delivery or not buyer_name:
            await cb.answer("Данные заказа неполны. Начните сначала.", show_alert=True)
            await state.clear()
            return

        # Validate cart is not empty before finalizing
        cart_items = await cart_store.get_cart(cb.from_user.id)
        if not cart_items:
            await cb.answer("Корзина пуста. Начните сначала.", show_alert=True)
            await state.clear()
            return

        await cb.answer()
        await finalize_checkout(
            cb.from_user.id, phone, buyer_name, delivery_type_val, delivery, cb.message, state
        )

    @dp.callback_query(F.data == "checkout:edit:fio")
    async def checkout_edit_fio(cb: CallbackQuery, state: FSMContext):
        """Return to FIO input step."""
        await state.set_state(CheckoutState.fio)
        await cb.message.answer("👤 Введите новое ФИО получателя:")
        await cb.answer()

    @dp.callback_query(F.data == "checkout:edit:phone")
    async def checkout_edit_phone(cb: CallbackQuery, state: FSMContext):
        """Return to phone input step."""
        await state.set_state(CheckoutState.phone)
        await cb.message.answer("📞 Введите новый номер телефона:")
        await cb.answer()

    @dp.callback_query(F.data == "checkout:edit:delivery")
    async def checkout_edit_delivery(cb: CallbackQuery, state: FSMContext):
        """Return to delivery type selection."""
        await state.set_state(CheckoutState.delivery_type)
        await cb.message.answer("📦 Выберите способ доставки:", reply_markup=delivery_type_kb())
        await cb.answer()
