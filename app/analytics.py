"""PostHog analytics wrapper for shop bot."""
import posthog
import logging

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
            properties={**(properties or {}), "bot": "shop"},
        )
    except Exception as e:
        logger.warning(f"PostHog track error: {e}")


def identify(user_id: int, properties: dict | None = None):
    """Identify user with properties."""
    try:
        posthog.identify(str(user_id), properties or {})
    except Exception as e:
        logger.warning(f"PostHog identify error: {e}")


def alias(user_id: int, website_distinct_id: str):
    """Link Telegram user to website visitor."""
    try:
        posthog.alias(previous_id=website_distinct_id, distinct_id=str(user_id))
    except Exception as e:
        logger.warning(f"PostHog alias error: {e}")
