"""AI manager handlers."""

from __future__ import annotations

import logging

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message

from .. import cart_store
from ..ai_manager import run_ai
from ..config import Settings
from ..keyboards import cart_kb
from ..services import CartService, ProductService

logger = logging.getLogger(__name__)


def register_ai_handlers(
    dp: Dispatcher,
    product_service: ProductService,
    cart_service: CartService,
) -> None:
    """Register AI manager handlers."""

    @dp.message(F.text == "🤖 AI Менеджер")
    async def text_ai(m: Message):
        await cart_store.set_ai_mode(m.from_user.id, True)
        await m.answer(
            "🤖 *AI Менеджер включён!*\n\n"
            "Напишите что вам нужно, например:\n"
            "• «Что у вас есть?»\n"
            "• «Покажи махорку»\n"
            "• «Добавь PRD-001, 5 штук»",
            parse_mode="HTML",
        )

    @dp.callback_query(F.data == "mode:ai")
    async def ai_mode_cb(cb: CallbackQuery):
        await cart_store.set_ai_mode(cb.from_user.id, True)
        await cb.message.answer(
            "🤖 Режим ИИ-менеджера включён. Напишите, что вам нужно (например: «нужен товар 1, 5 штук»)."
        )
        await cb.answer()

    @dp.message()
    async def any_text(m: Message):
        logger.debug(f"any_text called, text={m.text}")

        # Check if user is in AI mode
        ai_mode = await cart_store.get_ai_mode(m.from_user.id)
        logger.debug(f"ai_mode={ai_mode}")
        if not ai_mode:
            return

        cfg = Settings()
        logger.debug(f"openai_api_key exists: {bool(cfg.openai_api_key)}")
        if not cfg.openai_api_key:
            await m.answer(
                "ИИ-режим отключен: не задан OPENAI_API_KEY. Можно пользоваться каталогом кнопками."
            )
            return

        logger.debug("Calling run_ai...")

        # Tool implementations
        async def tool_search(args):
            q = str(args.get("query", "")).strip().lower()
            found = product_service.search(q)
            return {
                "results": [
                    {k: p[k] for k in ("sku", "name", "price_rub", "stock")} for p in found[:10]
                ]
            }

        async def tool_add(args):
            sku = str(args.get("sku", "")).strip()
            qty = int(args.get("qty", 1))
            logger.debug(f"Adding to cart: user_id={m.from_user.id}, sku={sku}, qty={qty}")

            success, message = await cart_service.add_to_cart(m.from_user.id, sku, qty)
            logger.debug(f"add_to_cart result: success={success}, message={message}")

            if success:
                return {"ok": True, "added": {"sku": sku, "qty": qty}}
            else:
                return {"ok": False, "error": message}

        async def tool_cart(args):
            summary = await cart_service.get_cart_summary(m.from_user.id)
            return {
                "lines": summary.lines,
                "total": summary.total,
                "items_count": len(summary.items),
            }

        async def tool_checkout_hint(args):
            return {
                "hint": "Нажмите «Корзина» → «Оформить». Понадобится телефон и строка доставки (город/ПВЗ)."
            }

        async def tool_list_all(args):
            products = product_service.get_available_products()
            result = [
                {
                    "sku": p["sku"],
                    "name": p["name"],
                    "price_rub": p["price_rub"],
                    "stock": p["stock"],
                    "tags": p.get("tags", ""),
                }
                for p in products
            ]
            return {"products": result, "total_count": len(result)}

        tool_impl = {
            "search_products": tool_search,
            "add_to_cart": tool_add,
            "show_cart": tool_cart,
            "checkout_hint": tool_checkout_hint,
            "list_all_products": tool_list_all,
        }

        # Get chat history
        history = await cart_store.get_chat_history(m.from_user.id)

        # Save user message to history
        await cart_store.add_chat_message(m.from_user.id, "user", m.text or "")

        # CRM: Log message if user has consent
        try:
            if await cart_store.has_user_consent(m.from_user.id):
                await cart_store.log_crm_message(
                    m.from_user.id,
                    direction='in',
                    text=m.text or "",
                    message_type='text',
                )
        except Exception as e:
            logger.warning(f"Failed to log CRM message: {e}")

        out = await run_ai(
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            user_text=m.text or "",
            tool_impl=tool_impl,
            history=history,
        )

        response_text = out.get("text", "")

        # Save AI response to history
        if response_text:
            await cart_store.add_chat_message(m.from_user.id, "assistant", response_text)
            await m.answer(response_text, parse_mode="HTML")

            # CRM: Log outgoing message if user has consent
            try:
                if await cart_store.has_user_consent(m.from_user.id):
                    await cart_store.log_crm_message(
                        m.from_user.id,
                        direction='out',
                        text=response_text,
                        message_type='ai_response',
                    )
            except Exception as e:
                logger.warning(f"Failed to log CRM outgoing message: {e}")

        # Show quick actions after AI response
        await m.answer("👇 Быстрые действия:", reply_markup=cart_kb())
