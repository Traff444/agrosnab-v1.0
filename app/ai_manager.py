from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Request timeout for OpenAI API calls
OPENAI_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

SYSTEM_PROMPT = """Ты — AI-продавец оптового магазина табачных изделий в Telegram.

⚠️ КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО:
- ВСЕГДА сначала вызывай list_all_products чтобы получить реальные SKU товаров
- Используй ТОЛЬКО те SKU, которые вернула функция list_all_products (например: PRD-001, PRD-002)
- НИКОГДА не выдумывай SKU! Если SKU не получен от list_all_products — не добавляй товар!

ПОРЯДОК РАБОТЫ:
1. list_all_products → получаешь список товаров с их реальными SKU
2. Находишь нужный товар по названию → берёшь его SKU из результата
3. add_to_cart(sku="PRD-XXX", qty=N) → используешь ТОЛЬКО реальный SKU
4. Отвечаешь клиенту что добавлено

ПОНИМАЙ НАЗВАНИЯ:
- "золотая" → Махорка Золотая
- "СССР" → Махорка СССР

ФОРМАТ ОТВЕТА:
- Не показывай техническую информацию клиенту
- После добавления: "✅ Добавил [товар] × [кол-во] шт!"
- Предлагай оформить заказ
"""


def build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_products",
                "description": "Поиск товаров по строке (название/теги). Возвращает список товаров с SKU, названием, ценой и остатком.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_to_cart",
                "description": "Добавить товар в корзину по SKU и количеству.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string"},
                        "qty": {"type": "integer", "minimum": 1},
                    },
                    "required": ["sku", "qty"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "show_cart",
                "description": "Показать корзину (позиции и суммы).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "checkout_hint",
                "description": "Подсказать пользователю как оформить заказ (какие данные нужны).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_all_products",
                "description": "Получить полный список всех товаров с ценами и остатками. Используй когда покупатель спрашивает 'что есть?', 'какой ассортимент?', 'покажи всё'.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


async def run_ai(
    *,
    api_key: str,
    model: str,
    user_text: str,
    tool_impl: dict[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]],
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Возвращает dict: {"text": str}"""
    client = AsyncOpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT)
    tools = build_tools()

    # Строим сообщения: системный промпт + история + новое сообщение
    messages: list[Any] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_text})

    max_iterations = 5

    try:
        for iteration in range(max_iterations):
            logger.debug(
                "Iteration %d: Sending request to %s with %d messages",
                iteration + 1,
                model,
                len(messages),
            )

            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            msg = resp.choices[0].message

            if not msg.tool_calls:
                logger.debug(
                    "No tool calls, returning: %s...",
                    (msg.content or "")[:100],
                )
                return {"text": msg.content or ""}

            logger.debug("Executing %d tool calls", len(msg.tool_calls))
            messages.append(msg)

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args_str = tool_call.function.arguments or "{}"
                logger.debug("Tool call: %s(%s)", name, args_str)

                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}

                if name in tool_impl:
                    result = await tool_impl[name](args)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return {"text": "Достигнут лимит обработки. Попробуйте ещё раз."}

    except Exception as e:
        logger.error("AI error: %s", e, exc_info=True)
        return {"text": f"❌ Ошибка AI: {str(e)}"}
