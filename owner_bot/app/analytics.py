"""PostHog analytics wrapper for owner bot."""

import logging

import posthog

logger = logging.getLogger(__name__)

POSTHOG_API_KEY = "phc_aycG7BYsQyyAO8N6NVCRnXrgjeMpw1BtCZD8SzpqZZB"
POSTHOG_HOST = "https://eu.i.posthog.com"


def init_posthog():
    posthog.project_api_key = POSTHOG_API_KEY
    posthog.host = POSTHOG_HOST
    posthog.debug = False
    logger.info("PostHog initialized")


def shutdown_posthog():
    posthog.shutdown()


def track(user_id: int, event: str, properties: dict | None = None):
    """Track event for a Telegram user."""
    try:
        posthog.capture(
            distinct_id=str(user_id),
            event=event,
            properties={**(properties or {}), "bot": "owner"},
        )
    except Exception as e:
        logger.warning(f"PostHog track error: {e}")
