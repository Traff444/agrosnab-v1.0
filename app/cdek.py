"""СДЭК API v2 async client."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

# API URLs
CDEK_API_URL_PROD = "https://api.cdek.ru/v2"
CDEK_API_URL_TEST = "https://api.edu.cdek.ru/v2"

# Token endpoint is the same for both environments
CDEK_AUTH_URL_PROD = "https://api.cdek.ru/v2/oauth/token"
CDEK_AUTH_URL_TEST = "https://api.edu.cdek.ru/v2/oauth/token"

# Default timeout for API requests
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass
class CdekCity:
    """City from CDEK API."""

    code: int
    city: str
    region: str
    country: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> CdekCity:
        return cls(
            code=data.get("code", 0),
            city=data.get("city", ""),
            region=data.get("region", ""),
            country=data.get("country", "Россия"),
        )

    def display_name(self) -> str:
        """Format for display in bot."""
        if self.region:
            return f"{self.city}, {self.region}"
        return self.city


@dataclass
class CdekPvz:
    """Pickup point (PVZ) from CDEK API."""

    code: str
    name: str
    address: str
    city: str
    work_time: str
    nearest_metro: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> CdekPvz:
        location = data.get("location", {})
        return cls(
            code=data.get("code", ""),
            name=data.get("name", ""),
            address=location.get("address_full", location.get("address", "")),
            city=location.get("city", ""),
            work_time=data.get("work_time", ""),
            nearest_metro=data.get("nearest_metro_station"),
        )

    def display_name(self) -> str:
        """Short display name for button."""
        # Truncate address if too long
        addr = self.address
        if len(addr) > 40:
            addr = addr[:37] + "..."
        return addr

    def full_display(self) -> str:
        """Full display for confirmation."""
        parts = [f"📍 {self.address}"]
        if self.work_time:
            parts.append(f"🕐 {self.work_time}")
        if self.nearest_metro:
            parts.append(f"🚇 {self.nearest_metro}")
        return "\n".join(parts)


class CdekClient:
    """Async client for CDEK API v2."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        test_mode: bool = True,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.test_mode = test_mode

        self._base_url = CDEK_API_URL_TEST if test_mode else CDEK_API_URL_PROD
        self._auth_url = CDEK_AUTH_URL_TEST if test_mode else CDEK_AUTH_URL_PROD

        # Token cache
        self._token: str | None = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        """Get OAuth token, using cache if valid."""
        # Check if we have a valid cached token (with 60s buffer)
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        logger.debug("Fetching new CDEK OAuth token")

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(
                self._auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._token = data["access_token"]
        # expires_in is in seconds
        self._token_expires_at = time.time() + data.get("expires_in", 3600)

        logger.debug("CDEK token obtained, expires in %d seconds", data.get("expires_in", 3600))
        return self._token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated API request."""
        token = await self._get_token()
        url = f"{self._base_url}/{endpoint}"

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def search_cities(self, query: str, limit: int = 10) -> list[CdekCity]:
        """
        Search cities by name.

        Args:
            query: City name to search
            limit: Maximum results to return

        Returns:
            List of matching cities
        """
        if not query or len(query) < 2:
            return []

        try:
            data = await self._request(
                "GET",
                "location/cities",
                params={
                    "city": query,
                    "size": limit,
                    "country_codes": "RU",  # Only Russia for now
                },
            )

            cities = []
            for item in data if isinstance(data, list) else []:
                try:
                    cities.append(CdekCity.from_api(item))
                except Exception as e:
                    logger.warning("Failed to parse city: %s", e)

            logger.debug("CDEK search_cities(%s): found %d results", query, len(cities))
            return cities

        except httpx.HTTPStatusError as e:
            logger.error("CDEK API error searching cities: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to search CDEK cities: %s", e)
            return []

    async def get_pvz_list(
        self,
        city_code: int,
        limit: int = 50,
    ) -> list[CdekPvz]:
        """
        Get list of pickup points (PVZ) in a city.

        Args:
            city_code: CDEK city code
            limit: Maximum results

        Returns:
            List of PVZ
        """
        try:
            data = await self._request(
                "GET",
                "deliverypoints",
                params={
                    "city_code": city_code,
                    "type": "PVZ",  # Only PVZ, not postomats
                    "size": limit,
                },
            )

            pvz_list = []
            for item in data if isinstance(data, list) else []:
                try:
                    pvz_list.append(CdekPvz.from_api(item))
                except Exception as e:
                    logger.warning("Failed to parse PVZ: %s", e)

            logger.debug("CDEK get_pvz_list(%d): found %d results", city_code, len(pvz_list))
            return pvz_list

        except httpx.HTTPStatusError as e:
            logger.error("CDEK API error getting PVZ list: %s", e)
            return []
        except Exception as e:
            logger.error("Failed to get CDEK PVZ list: %s", e)
            return []


# ---------------------------------------------------------------------------
# Demo client (no real CDEK API calls)
# ---------------------------------------------------------------------------


class CdekClientProtocol(Protocol):
    async def search_cities(self, query: str, limit: int = 10) -> list[CdekCity]: ...

    async def get_pvz_list(self, city_code: int, limit: int = 50) -> list[CdekPvz]: ...


def _demo_data() -> tuple[list[CdekCity], dict[int, list[CdekPvz]]]:
    """
    Return demo CDEK data (cities + PVZ).

    Notes:
    - City codes are arbitrary demo codes (ints).
    - PVZ codes are stable strings suitable for callback_data.
    """
    cities = [
        CdekCity(code=44, city="Москва", region="Москва", country="Россия"),
        CdekCity(code=137, city="Санкт‑Петербург", region="Санкт‑Петербург", country="Россия"),
        CdekCity(code=270, city="Екатеринбург", region="Свердловская обл.", country="Россия"),
        CdekCity(code=361, city="Новосибирск", region="Новосибирская обл.", country="Россия"),
        CdekCity(code=551, city="Казань", region="Республика Татарстан", country="Россия"),
    ]

    def pvz(
        code: str,
        name: str,
        address: str,
        city: str,
        work_time: str,
        nearest_metro: str | None = None,
    ) -> CdekPvz:
        return CdekPvz(
            code=code,
            name=name,
            address=address,
            city=city,
            work_time=work_time,
            nearest_metro=nearest_metro,
        )

    pvz_by_city: dict[int, list[CdekPvz]] = {
        44: [
            pvz("MSK001", "ПВЗ Москва • Тверская", "Москва, ул. Тверская, 7", "Москва", "09:00–21:00", "Тверская"),
            pvz(
                "MSK002",
                "ПВЗ Москва • Белорусская",
                "Москва, Ленинградский пр-т, 10",
                "Москва",
                "10:00–20:00",
                "Белорусская",
            ),
            pvz("MSK003", "ПВЗ Москва • Арбат", "Москва, ул. Арбат, 12", "Москва", "10:00–22:00", "Арбатская"),
            pvz(
                "MSK004",
                "ПВЗ Москва • Сити",
                "Москва, Пресненская наб., 12",
                "Москва",
                "09:00–21:00",
                "Деловой центр",
            ),
            pvz("MSK005", "ПВЗ Москва • Сокол", "Москва, ул. Ленинградская, 3", "Москва", "09:00–20:00", "Сокол"),
            pvz("MSK006", "ПВЗ Москва • Павелецкая", "Москва, ул. Дубининская, 11", "Москва", "10:00–21:00", "Павелецкая"),
            pvz(
                "MSK007",
                "ПВЗ Москва • Бауманская",
                "Москва, ул. Бауманская, 33",
                "Москва",
                "09:00–21:00",
                "Бауманская",
            ),
            pvz("MSK008", "ПВЗ Москва • Проспект Мира", "Москва, пр-т Мира, 21", "Москва", "10:00–20:00", "Проспект Мира"),
        ],
        137: [
            pvz("SPB001", "ПВЗ СПб • Невский", "Санкт‑Петербург, Невский пр-т, 28", "Санкт‑Петербург", "10:00–22:00", "Гостиный двор"),
            pvz("SPB002", "ПВЗ СПб • Петроградка", "Санкт‑Петербург, Каменноостровский пр-т, 42", "Санкт‑Петербург", "09:00–21:00", "Петроградская"),
            pvz("SPB003", "ПВЗ СПб • Московские ворота", "Санкт‑Петербург, Московский пр-т, 105", "Санкт‑Петербург", "10:00–20:00", "Московские ворота"),
            pvz("SPB004", "ПВЗ СПб • Васильевский", "Санкт‑Петербург, 6-я линия В.О., 25", "Санкт‑Петербург", "10:00–21:00", "Василеостровская"),
            pvz("SPB005", "ПВЗ СПб • Ладожская", "Санкт‑Петербург, Заневский пр-т, 65", "Санкт‑Петербург", "09:00–21:00", "Ладожская"),
            pvz("SPB006", "ПВЗ СПб • Купчино", "Санкт‑Петербург, ул. Ярослава Гашека, 5", "Санкт‑Петербург", "10:00–20:00", "Купчино"),
        ],
        270: [
            pvz("EKB001", "ПВЗ Екб • Центр", "Екатеринбург, ул. Ленина, 25", "Екатеринбург", "09:00–21:00"),
            pvz("EKB002", "ПВЗ Екб • Уралмаш", "Екатеринбург, ул. Победы, 43", "Екатеринбург", "10:00–20:00"),
            pvz("EKB003", "ПВЗ Екб • Вокзал", "Екатеринбург, ул. Челюскинцев, 106", "Екатеринбург", "09:00–20:00"),
            pvz("EKB004", "ПВЗ Екб • Академический", "Екатеринбург, ул. Вильгельма де Геннина, 40", "Екатеринбург", "10:00–21:00"),
            pvz("EKB005", "ПВЗ Екб • Юго‑Запад", "Екатеринбург, ул. Шаумяна, 83", "Екатеринбург", "10:00–20:00"),
            pvz("EKB006", "ПВЗ Екб • Эльмаш", "Екатеринбург, ул. Старых Большевиков, 29", "Екатеринбург", "09:00–21:00"),
        ],
        361: [
            pvz("NSK001", "ПВЗ Нск • Красный проспект", "Новосибирск, Красный пр-т, 50", "Новосибирск", "09:00–21:00"),
            pvz("NSK002", "ПВЗ Нск • Площадь Ленина", "Новосибирск, ул. Советская, 18", "Новосибирск", "10:00–20:00"),
            pvz("NSK003", "ПВЗ Нск • Заельцовский", "Новосибирск, ул. Дуси Ковальчук, 179", "Новосибирск", "09:00–20:00"),
            pvz("NSK004", "ПВЗ Нск • Октябрьский", "Новосибирск, ул. Кирова, 113", "Новосибирск", "10:00–21:00"),
            pvz("NSK005", "ПВЗ Нск • Левый берег", "Новосибирск, ул. Станиславского, 14", "Новосибирск", "09:00–21:00"),
            pvz("NSK006", "ПВЗ Нск • Калининский", "Новосибирск, ул. Богдана Хмельницкого, 22", "Новосибирск", "10:00–20:00"),
        ],
        551: [
            pvz("KZN001", "ПВЗ Казань • Баумана", "Казань, ул. Баумана, 15", "Казань", "10:00–22:00"),
            pvz("KZN002", "ПВЗ Казань • Кремлёвская", "Казань, ул. Кремлёвская, 21", "Казань", "09:00–21:00"),
            pvz("KZN003", "ПВЗ Казань • Проспект Победы", "Казань, пр-т Победы, 78", "Казань", "10:00–20:00"),
            pvz("KZN004", "ПВЗ Казань • Ямашева", "Казань, пр-т Ямашева, 46", "Казань", "09:00–21:00"),
            pvz("KZN005", "ПВЗ Казань • Горки", "Казань, ул. Рихарда Зорге, 66", "Казань", "10:00–20:00"),
            pvz("KZN006", "ПВЗ Казань • Квартал", "Казань, ул. Чистопольская, 7", "Казань", "10:00–21:00"),
        ],
    }

    # Ensure we are within 20–40 PVZ total.
    # Current: 8 + 6 + 6 + 6 + 6 = 32
    return cities, pvz_by_city


class DemoCdekClient:
    """Demo client that mimics CDEK interface without any HTTP calls."""

    def __init__(self) -> None:
        self._cities, self._pvz_by_city = _demo_data()

    async def search_cities(self, query: str, limit: int = 10) -> list[CdekCity]:
        q = (query or "").strip()
        if len(q) < 2:
            return []
        ql = q.lower()
        items = [c for c in self._cities if ql in c.city.lower()]
        return items[: max(0, int(limit or 0))]

    async def get_pvz_list(self, city_code: int, limit: int = 50) -> list[CdekPvz]:
        items = self._pvz_by_city.get(int(city_code), [])
        return items[: max(0, int(limit or 0))]


# Singleton instance (initialized on first use)
_cdek_client: CdekClientProtocol | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_cdek_client() -> CdekClientProtocol | None:
    """
    Get or create CDEK client singleton.

    Priority:
    - If credentials are configured -> real API client
    - Else, if demo mode enabled -> demo client
    - Else -> None
    """
    global _cdek_client

    if _cdek_client is not None:
        return _cdek_client

    from .config import Settings

    cfg = None
    try:
        cfg = Settings()
    except Exception:
        # In unit-tests or partial environments Settings() may fail because unrelated
        # required env vars (e.g. TELEGRAM_BOT_TOKEN) are not set.
        cfg = None

    # Prefer real client if credentials exist
    if cfg and cfg.cdek_enabled():
        _cdek_client = CdekClient(
            client_id=cfg.cdek_client_id,  # type: ignore
            client_secret=cfg.cdek_client_secret,  # type: ignore
            test_mode=cfg.cdek_test_mode,
        )
        logger.info("CDEK client initialized (test_mode=%s)", cfg.cdek_test_mode)
        return _cdek_client

    # Fallback to reading only CDEK-related env vars if full Settings is unavailable.
    client_id = (cfg.cdek_client_id if cfg else os.getenv("CDEK_CLIENT_ID")) if cfg else os.getenv("CDEK_CLIENT_ID")
    client_secret = (
        (cfg.cdek_client_secret if cfg else os.getenv("CDEK_CLIENT_SECRET"))
        if cfg
        else os.getenv("CDEK_CLIENT_SECRET")
    )
    test_mode = cfg.cdek_test_mode if cfg else _env_bool("CDEK_TEST_MODE", True)
    demo_mode = cfg.cdek_demo_mode if cfg else _env_bool("CDEK_DEMO_MODE", False)

    if client_id and client_secret:
        _cdek_client = CdekClient(client_id=str(client_id), client_secret=str(client_secret), test_mode=test_mode)
        logger.info("CDEK client initialized (test_mode=%s)", test_mode)
        return _cdek_client

    if demo_mode:
        _cdek_client = DemoCdekClient()
        logger.info("CDEK demo mode enabled (no credentials configured)")
        return _cdek_client

    logger.info("CDEK integration disabled (credentials not configured)")
    return None
