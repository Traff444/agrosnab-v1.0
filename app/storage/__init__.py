"""Storage package for SQLite-backed data.

This package provides modular storage for:
- db.py: Database configuration and initialization
- cart.py: Shopping cart and checkout sessions
- chat_history.py: AI chat history
- crm.py: CRM events and messages
"""

from .cart import (
    CartItem,
    OrderIdGenerator,
    add_to_cart,
    cleanup_old_checkout_sessions,
    clear_cart,
    compute_cart_hash,
    get_cart,
    get_or_create_checkout_session,
    mark_checkout_complete,
    remove_from_cart,
    set_qty,
)
from .chat_history import (
    MAX_HISTORY_MESSAGES,
    ChatMessage,
    MessageRole,
    add_chat_message,
    clear_chat_history,
    get_ai_mode,
    get_chat_history,
    set_ai_mode,
)
from .crm import (
    EVENT_TO_STAGE,
    MAX_CRM_MESSAGES,
    STAGE_PRIORITY,
    CrmEvent,
    CrmMessage,
    CrmStage,
    DailyStats,
    EventType,
    MessageDirection,
    MessageType,
    compute_stage,
    format_messages_for_ai,
    get_daily_stats,
    get_first_seen,
    get_last_seen,
    get_user_events,
    get_user_messages,
    get_user_messages_count,
    get_user_orders_count,
    get_user_stage,
    has_user_consent,
    log_crm_event,
    log_crm_message,
)
from .db import DB_PATH, init_db

__all__ = [
    # Database
    "DB_PATH",
    "init_db",
    # Cart types
    "CartItem",
    "OrderIdGenerator",
    # Cart functions
    "add_to_cart",
    "set_qty",
    "remove_from_cart",
    "clear_cart",
    "get_cart",
    "compute_cart_hash",
    "get_or_create_checkout_session",
    "mark_checkout_complete",
    "cleanup_old_checkout_sessions",
    # Chat history types
    "MessageRole",
    "ChatMessage",
    # Chat history functions
    "MAX_HISTORY_MESSAGES",
    "add_chat_message",
    "get_chat_history",
    "clear_chat_history",
    "set_ai_mode",
    "get_ai_mode",
    # CRM types
    "CrmStage",
    "EventType",
    "MessageDirection",
    "MessageType",
    "CrmEvent",
    "CrmMessage",
    "DailyStats",
    # CRM constants
    "STAGE_PRIORITY",
    "EVENT_TO_STAGE",
    "MAX_CRM_MESSAGES",
    # CRM functions
    "log_crm_event",
    "get_user_events",
    "get_user_stage",
    "get_user_orders_count",
    "get_daily_stats",
    "get_first_seen",
    "get_last_seen",
    "compute_stage",
    "log_crm_message",
    "get_user_messages",
    "get_user_messages_count",
    "has_user_consent",
    "format_messages_for_ai",
]
