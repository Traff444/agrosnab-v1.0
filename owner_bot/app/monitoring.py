"""Monitoring utilities: alerts, retry logic, error tracking."""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import sentry_sdk
from aiogram import Bot
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


async def alert_owner(bot: Bot, message: str) -> None:
    """Send alert to all bot owners."""
    settings = get_settings()
    for owner_id in settings.owner_telegram_ids:
        try:
            await bot.send_message(owner_id, f"🚨 {message}")
        except Exception as e:
            logger.warning("alert_send_failed", extra={"owner_id": owner_id, "error": str(e)})


def capture_exception(error: Exception, context: dict | None = None) -> None:
    """Capture exception to Sentry if configured."""
    settings = get_settings()
    if settings.sentry_dsn:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(error)
    logger.error("error_captured", extra={"error_type": type(error).__name__, "error": str(error)}, exc_info=error)


# Transient errors worth retrying (network issues, rate limits, server errors)
RETRYABLE_EXCEPTIONS = (
    HttpError,          # Google API errors (429, 500, 503)
    ConnectionError,    # Network connection issues
    TimeoutError,       # Request timeouts
    OSError,            # Low-level network errors (includes ssl.SSLError)
)

# Retry decorator for Google API calls
google_api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying {retry_state.fn.__name__} after error: {retry_state.outcome.exception()}, "
        f"attempt {retry_state.attempt_number}/3"
    ),
)


def with_error_capture(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorator to capture errors to Sentry for async functions."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            capture_exception(e, {"function": func.__name__})
            raise

    return wrapper
