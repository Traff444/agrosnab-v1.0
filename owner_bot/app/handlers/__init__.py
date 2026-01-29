"""Telegram bot handlers."""

from aiogram import Router

from app.handlers.critical import router as critical_router
from app.handlers.start import router as start_router
from app.handlers.intake import router as intake_router
from app.handlers.products import router as products_router
from app.handlers.orders import router as orders_router
from app.handlers.health import router as health_router
from app.handlers.crm import router as crm_router
from app.handlers.stock import router as stock_router


def get_main_router() -> Router:
    """Create and configure main router with all sub-routers."""
    main_router = Router()

    # Critical commands FIRST - always work regardless of FSM state
    main_router.include_router(critical_router)

    # Order matters: more specific handlers first
    main_router.include_router(health_router)
    main_router.include_router(intake_router)
    main_router.include_router(products_router)
    main_router.include_router(stock_router)
    main_router.include_router(orders_router)
    main_router.include_router(crm_router)
    main_router.include_router(start_router)

    return main_router


__all__ = ["get_main_router"]
