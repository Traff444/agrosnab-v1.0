"""FSM states for product operations."""

from aiogram.fsm.state import State, StatesGroup


class ProductState(StatesGroup):
    """FSM states for product operations."""

    searching = State()
    viewing = State()


class StockOperationState(StatesGroup):
    """FSM states for stock operations (writeoff, correction, archive)."""

    # Writeoff (Списание)
    writeoff_qty = State()
    writeoff_reason = State()
    writeoff_confirm = State()

    # Correction (Корректировка)
    correction_qty = State()
    correction_reason = State()
    correction_confirm = State()

    # Archive (Архивация)
    archive_menu = State()
    archive_confirm = State()
