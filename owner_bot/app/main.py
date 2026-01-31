"""Main entry point for the Owner Bot."""

import asyncio
import logging
import sys
from pathlib import Path

import sentry_sdk
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers import get_main_router
from app.security import WhitelistMiddleware
from app.sheets import sheets_client


def setup_logging() -> None:
    """Configure logging based on settings."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Reduce noise from libraries
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


async def on_startup(bot: Bot) -> None:
    """Startup tasks."""
    logger = logging.getLogger(__name__)

    # Ensure directories exist
    settings = get_settings()
    Path(settings.tmp_dir).mkdir(exist_ok=True)
    Path(settings.db_path).parent.mkdir(exist_ok=True)

    # Load column mapping from Sheets
    try:
        col_map = await sheets_client.load_column_map()
        logger.info(
            "column_map_loaded",
            extra={"columns_count": len(col_map)},
        )
    except Exception as e:
        logger.error(
            "column_map_load_failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        logger.warning("Bot will start but Sheets operations may fail")

    # Get bot info
    me = await bot.get_me()
    logger.info(
        "bot_started",
        extra={"username": me.username, "bot_id": me.id},
    )

    settings = get_settings()
    logger.info(
        "owners_configured",
        extra={"owner_ids": settings.owner_telegram_ids},
    )


async def on_shutdown(bot: Bot) -> None:
    """Shutdown tasks."""
    logger = logging.getLogger(__name__)
    logger.info("Bot shutting down...")

    # Close bot session
    await bot.session.close()


def setup_sentry() -> None:
    """Initialize Sentry SDK if DSN is configured."""
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logging.getLogger(__name__).info(
            f"Sentry initialized for environment: {settings.environment}"
        )


async def main() -> None:
    """Main async entry point."""
    setup_logging()
    setup_sentry()
    logger = logging.getLogger(__name__)

    settings = get_settings()

    # Validate required settings
    if not settings.owner_telegram_ids:
        logger.error("OWNER_TELEGRAM_IDS not configured!")
        sys.exit(1)

    # Create bot and dispatcher
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middleware
    dp.message.middleware(WhitelistMiddleware())
    dp.callback_query.middleware(WhitelistMiddleware())

    # Register routers
    dp.include_router(get_main_router())

    # Register lifecycle handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting bot polling...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
