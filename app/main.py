"""Main bot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent

from . import cart_store
from .config import Settings
from .handlers import (
    register_ai_handlers,
    register_cart_handlers,
    register_catalog_handlers,
    register_start_handlers,
)
from .services import CartService, ProductService
from .sheets import SheetsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def global_error_handler(event: ErrorEvent) -> bool:
    """Global error handler for all unhandled exceptions."""
    logger.error(
        "Unhandled exception in handler",
        exc_info=event.exception,
        extra={
            "update": event.update,
        },
    )

    # Try to notify user
    try:
        update = event.update
        if update.message:
            await update.message.answer(
                "❌ Произошла ошибка. Попробуйте ещё раз или используйте /start"
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "Произошла ошибка. Попробуйте ещё раз.", show_alert=True
            )
    except Exception as e:
        logger.error(f"Failed to notify user about error: {e}")

    return True  # Error was handled


async def main():
    """Main application entry point."""
    logger.info("Starting bot...")

    # Load config
    cfg = Settings()
    logger.info(f"Loaded config: sheet_id={cfg.sheet_id()[:10]}...")

    # Initialize bot and dispatcher
    bot = Bot(token=cfg.telegram_bot_token)
    dp = Dispatcher()

    # Ensure polling works even if webhook was previously set for this bot token
    try:
        me = await bot.get_me()
        logger.info("Bot identity: @%s (%s)", me.username, me.id)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted (drop_pending_updates=True)")
    except Exception as e:
        logger.error("Failed to initialize bot (get_me/delete_webhook): %s", e)
        raise

    # Register global error handler
    dp.error.register(global_error_handler)

    # Initialize Google Sheets client
    sheets = SheetsClient(cfg.sheet_id(), cfg.google_service_account_json_path)
    logger.info("Google Sheets client initialized")

    # Initialize services
    product_service = ProductService(sheets)
    cart_service = CartService(product_service)
    logger.info("Services initialized")

    # Initialize database
    await cart_store.init_db()
    logger.info("Database initialized")

    # Register handlers
    # Order matters! More specific handlers should be registered first
    register_start_handlers(dp, product_service, sheets)
    register_catalog_handlers(dp, product_service, sheets)
    register_cart_handlers(dp, product_service, cart_service, sheets)
    register_ai_handlers(dp, product_service, cart_service)  # Must be last (catch-all)
    logger.info("Handlers registered")

    # Start polling
    logger.info("Bot started, polling for updates...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
