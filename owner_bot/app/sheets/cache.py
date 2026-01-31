"""TTL cache for product data."""

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Simple TTL cache for any data type."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: T | None = None
        self._cached_at: float = 0
        self._ttl = ttl_seconds

    def get(self) -> T | None:
        """Get cached data if not expired."""
        if self._cache is not None and time.time() - self._cached_at < self._ttl:
            return self._cache
        return None

    def set(self, data: T) -> None:
        """Store data in cache."""
        self._cache = data
        self._cached_at = time.time()

    def invalidate(self) -> None:
        """Clear the cache."""
        self._cache = None
        self._cached_at = 0

    @property
    def is_valid(self) -> bool:
        """Check if cache has valid data."""
        return self._cache is not None and time.time() - self._cached_at < self._ttl

    @property
    def age_seconds(self) -> float:
        """Get cache age in seconds."""
        if self._cached_at == 0:
            return float("inf")
        return time.time() - self._cached_at
