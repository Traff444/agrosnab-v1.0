"""Product handlers package.

This package contains handlers for product operations:
- search: Product search and display
- card: Product card actions (intake, photo, edit, more menu)
- writeoff: Stock writeoff flow
- correction: Stock correction flow
- archive: Product archivation flow
- confirmation: Action confirmation handlers
- navigation: Navigation callbacks
"""

from aiogram import Router

from . import archive, card, confirmation, correction, navigation, search, writeoff
from .states import ProductState, StockOperationState

# Create main router and include all sub-routers
router = Router()
router.include_router(search.router)
router.include_router(card.router)
router.include_router(writeoff.router)
router.include_router(correction.router)
router.include_router(archive.router)
router.include_router(confirmation.router)
router.include_router(navigation.router)

__all__ = [
    "router",
    "ProductState",
    "StockOperationState",
]
