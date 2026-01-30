"""Cart and checkout handlers."""

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from .. import cart_store
from ..config import Settings
from ..cdek import CdekPvz, get_cdek_client
from ..invoice import generate_invoice_pdf
from ..keyboards import city_select_kb, delivery_confirm_kb, pvz_select_kb
from ..services import CartService, ProductService
from ..sheets import SheetsClient, retry_async
from ..utils import make_order_id, validate_phone

logger = logging.getLogger(__name__)


class CheckoutState(StatesGroup):
    phone = State()
    city_input = State()
    city_select = State()
    pvz_select = State()
    delivery_manual = State()  # fallback or manual entry


def register_cart_handlers(
    dp: Dispatcher,
    product_service: ProductService,
    cart_service: CartService,
    sheets_client: SheetsClient,
) -> None:
    """Register cart and checkout handlers."""

    async def finalize_checkout(
        user_id: int,
        buyer_phone: str,
        delivery: str,
        message: Message,
        state: FSMContext,
    ) -> None:
        """Create invoice, write order to sheets, send PDF, clear cart and state."""
        products_by_sku = product_service.get_products_by_sku()
        cart_items = await cart_store.get_cart(user_id)

        if not cart_items:
            await message.answer("Корзина пуста. Начните сначала.")
            await state.clear()
            return

        _, total, _ = await cart_service.calc_cart_for_checkout(user_id)

        # Idempotent checkout: get or create session to avoid duplicate orders
        order_id, _ = await cart_store.get_or_create_checkout_session(
            user_id,
            cart_items,
            lambda: make_order_id("ORD"),
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
            buyer_phone=buyer_phone,
            delivery=delivery,
            items=items_for_pdf,
        )

        # write order to sheet (async with retry)
        order_row = [
            order_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            str(user_id),
            buyer_phone,
            "Счет выставлен",
            total,
            "СДЭК",
            delivery,
            "; ".join([f"{sku}:{qty}" for sku, qty in cart_items]),
            f"{invoice_no}.pdf",
        ]

        try:
            await retry_async(sheets_client.append_order, order_row)

            # optional spisanie (async with retry)
            cfg = Settings()
            if cfg.auto_write_spisanie:
                await retry_async(sheets_client.append_spisanie_rows, spisanie_rows)
                # Update stock in Склад sheet (now async with batch update)
                await retry_async(sheets_client.decrease_stock, [(sku, qty) for sku, qty in cart_items])
                # Invalidate cache after stock update
                product_service.invalidate_cache()

            # Mark checkout session as completed
            await cart_store.mark_checkout_complete(user_id, order_id)

            # CRM: Log order_created event
            await cart_store.log_crm_event(user_id, 'order_created', {
                'order_id': order_id,
                'total': total,
                'items_count': len(cart_items),
                'delivery': delivery,
            })

            # CRM: Update lead stage to customer or repeat
            orders_count = await cart_store.get_user_orders_count(user_id)
            stage = 'repeat' if orders_count >= 2 else 'customer'

            # Calculate lifetime value
            events = await cart_store.get_user_events(user_id, event_types=['order_created'])
            lifetime_value = sum(
                (e.get('payload') or {}).get('total', 0) for e in events
            )

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
                logger.warning(f"Failed to update lead {user_id}: {crm_error}")

        except Exception as e:
            logger.error("Checkout failed for user %s: %s", user_id, e)
            await message.answer(
                "❌ Ошибка при сохранении заказа. Попробуйте ещё раз или свяжитесь с поддержкой."
            )
            await state.clear()
            return

        await message.answer("✅ Счет сформирован. Отправляю PDF…")
        await message.answer_document(FSInputFile(out_pdf), caption=f"Счет № {invoice_no}")

        await cart_store.clear_cart(user_id)
        await cart_store.cleanup_old_checkout_sessions(user_id)
        await state.clear()

    @dp.message(F.text == "🧺 Корзина")
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
        except Exception:
            try:
                await cb.message.delete()
            except Exception:
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
            await cart_store.log_crm_event(user_id, 'add_to_cart', {
                'sku': sku,
                'qty': qty,
            })

            # CRM: Update lead stage to cart
            try:
                await sheets_client.upsert_lead(user_id, stage='cart')
            except Exception as e:
                logger.warning(f"Failed to update lead {user_id}: {e}")

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
            except Exception:
                pass
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
        except Exception:
            pass
        await cb.answer()

    @dp.callback_query(F.data.startswith("cart:remove:"))
    async def cart_remove(cb: CallbackQuery):
        sku = cb.data.split(":")[2]
        await cart_store.remove_from_cart(cb.from_user.id, sku)

        # Refresh cart display
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        text = cart_service.format_cart_text(summary)
        kb = cart_service.get_cart_keyboard(summary)
        try:
            await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
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
        except Exception:
            pass
        await cb.answer()

    @dp.callback_query(F.data == "checkout:start")
    async def checkout_start(cb: CallbackQuery, state: FSMContext):
        cart_items = await cart_store.get_cart(cb.from_user.id)
        if not cart_items:
            await cb.answer("Корзина пустая")
            return

        # min check
        summary = await cart_service.get_cart_summary(cb.from_user.id)
        if summary.below_min:
            await cb.answer(f"Минималка {summary.min_sum} ₽")
            return

        await state.set_state(CheckoutState.phone)
        await cb.message.answer("Введите номер телефона (пример: +79990000000):")
        await cb.answer()

    @dp.message(CheckoutState.phone)
    async def checkout_phone(m: Message, state: FSMContext):
        user_id = m.from_user.id
        raw_phone = (m.text or "").strip()
        is_valid, result = validate_phone(raw_phone)
        if not is_valid:
            await m.answer(f"❌ {result}\nПопробуйте ещё раз:")
            return  # Stay in phone state
        phone = result
        await state.update_data(phone=phone)

        # CRM: Log checkout_started event
        await cart_store.log_crm_event(user_id, 'checkout_started', {
            'phone': phone[:4] + '***' + phone[-2:] if len(phone) > 6 else '***',  # masked
        })

        # CRM: Update lead stage to checkout and save phone
        try:
            await sheets_client.upsert_lead(user_id, stage='checkout', phone=phone)
        except Exception as e:
            logger.warning(f"Failed to update lead {user_id}: {e}")
        cdek_client = get_cdek_client()
        # Если клиент СДЭК недоступен — идём по старой схеме (ручной ввод)
        # В demo mode клиент будет доступен даже без реальных кредов.
        if not cdek_client:
            await state.set_state(CheckoutState.delivery_manual)
            await m.answer(
                "Введите доставку/город/ПВЗ (текстом, например: «СДЭК, Москва, ПВЗ Тверская 7»):"
            )
            return

        await state.set_state(CheckoutState.city_input)
        await m.answer("Введите город (пример: Москва).")

    @dp.message(CheckoutState.delivery_manual)
    async def checkout_delivery_manual(m: Message, state: FSMContext):
        data = await state.get_data()
        phone = str(data.get("phone", "")).strip()
        delivery = (m.text or "").strip()
        await finalize_checkout(m.from_user.id, phone, delivery, m, state)

    @dp.message(CheckoutState.city_input)
    async def cdek_city_input(m: Message, state: FSMContext):
        q = (m.text or "").strip()
        if q.lower() in {"вручную", "manual"}:
            await state.set_state(CheckoutState.delivery_manual)
            await m.answer("Ок. Введите доставку/город/ПВЗ текстом:")
            return

        cdek_client = get_cdek_client()
        if not cdek_client:
            await state.set_state(CheckoutState.delivery_manual)
            await m.answer("СДЭК сейчас недоступен. Введите доставку/город/ПВЗ текстом:")
            return

        cities = await cdek_client.search_cities(q, limit=10)
        if not cities:
            await m.answer("Не нашёл город. Попробуйте ещё раз (пример: Москва) или напишите «вручную».")
            return

        city_items = [(c.code, c.display_name()) for c in cities if c.code]
        await state.update_data(cdek_cities=city_items)
        await state.set_state(CheckoutState.city_select)
        await m.answer("Выберите город:", reply_markup=city_select_kb(city_items))

    @dp.callback_query(F.data == "cdek:city:retry")
    async def cdek_retry_city(cb: CallbackQuery, state: FSMContext):
        await state.set_state(CheckoutState.city_input)
        await cb.message.answer("Введите город (пример: Москва).")
        await cb.answer()

    @dp.callback_query(F.data == "cdek:manual")
    async def cdek_manual(cb: CallbackQuery, state: FSMContext):
        await state.set_state(CheckoutState.delivery_manual)
        await cb.message.answer("Введите доставку/город/ПВЗ (текстом):")
        await cb.answer()

    @dp.callback_query(F.data.startswith("cdek:city:"))
    async def cdek_city_selected(cb: CallbackQuery, state: FSMContext):
        if cb.data == "cdek:city:retry":
            # This callback has its own dedicated handler above.
            await cb.answer()
            return
        # cdek:city:{city_code}
        try:
            city_code = int(cb.data.split(":")[2])
        except Exception:
            await cb.answer("Некорректный город", show_alert=True)
            return

        cdek_client = get_cdek_client()
        if not cdek_client:
            await state.set_state(CheckoutState.delivery_manual)
            await cb.message.answer("СДЭК сейчас недоступен. Введите доставку/город/ПВЗ текстом:")
            await cb.answer()
            return

        pvz = await cdek_client.get_pvz_list(city_code, limit=50)
        if not pvz:
            await cb.message.answer("В этом городе не нашёл ПВЗ. Попробуйте другой город или «вручную».")
            await cb.answer()
            return

        pvz_map: dict[str, dict] = {}
        pvz_items: list[tuple[str, str]] = []
        for p in pvz:
            if not p.code:
                continue
            pvz_map[p.code] = {
                "code": p.code,
                "name": p.name,
                "address": p.address,
                "city": p.city,
                "work_time": p.work_time,
                "nearest_metro": p.nearest_metro,
            }
            pvz_items.append((p.code, p.display_name()))

        await state.update_data(cdek_city_code=city_code, cdek_pvz_map=pvz_map, cdek_pvz_items=pvz_items)
        await state.set_state(CheckoutState.pvz_select)
        await cb.message.answer("Выберите ПВЗ:", reply_markup=pvz_select_kb(pvz_items, city_code=city_code, page=0))
        await cb.answer()

    @dp.callback_query(F.data.startswith("cdek:pvz_page:"))
    async def cdek_pvz_page(cb: CallbackQuery, state: FSMContext):
        # cdek:pvz_page:{city_code}:{page}
        parts = cb.data.split(":")
        if len(parts) != 4:
            await cb.answer()
            return
        try:
            city_code = int(parts[2])
            page = int(parts[3])
        except Exception:
            await cb.answer()
            return

        data = await state.get_data()
        pvz_items = data.get("cdek_pvz_items", [])
        if not pvz_items:
            await cb.answer("Список ПВЗ не найден. Начните заново.", show_alert=True)
            await state.set_state(CheckoutState.city_input)
            return

        try:
            await cb.message.edit_reply_markup(reply_markup=pvz_select_kb(pvz_items, city_code=city_code, page=page))
        except Exception:
            await cb.message.answer("Выберите ПВЗ:", reply_markup=pvz_select_kb(pvz_items, city_code=city_code, page=page))
        await cb.answer()

    @dp.callback_query(F.data.startswith("cdek:pvz:"))
    async def cdek_pvz_selected(cb: CallbackQuery, state: FSMContext):
        # cdek:pvz:{pvz_code}
        pvz_code = cb.data.split(":")[2] if cb.data else ""
        data = await state.get_data()
        pvz_map = data.get("cdek_pvz_map", {}) or {}
        pvz_data = pvz_map.get(pvz_code)
        if not pvz_data:
            await cb.answer("ПВЗ не найден. Попробуйте ещё раз.", show_alert=True)
            return

        await state.update_data(cdek_selected_pvz=pvz_data)

        pvz_obj = CdekPvz(
            code=pvz_data.get("code", ""),
            name=pvz_data.get("name", ""),
            address=pvz_data.get("address", ""),
            city=pvz_data.get("city", ""),
            work_time=pvz_data.get("work_time", ""),
            nearest_metro=pvz_data.get("nearest_metro"),
        )
        await cb.message.answer(f"Проверьте ПВЗ:\n\n{pvz_obj.full_display()}", reply_markup=delivery_confirm_kb())
        await cb.answer()

    @dp.callback_query(F.data == "cdek:confirm")
    async def cdek_confirm(cb: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        phone = str(data.get("phone", "")).strip()
        pvz_data = data.get("cdek_selected_pvz")
        if not pvz_data:
            await cb.answer("Сначала выберите ПВЗ", show_alert=True)
            return

        address = str(pvz_data.get("address", "")).strip()
        code = str(pvz_data.get("code", "")).strip()
        delivery = f"ПВЗ СДЭК: {address} ({code})" if code else f"ПВЗ СДЭК: {address}"

        await cb.answer()
        await finalize_checkout(cb.from_user.id, phone, delivery, cb.message, state)
