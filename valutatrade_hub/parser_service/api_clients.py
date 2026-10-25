"""Unified clients for CoinGecko and ExchangeRate-API."""

from abc import ABC, abstractmethod
import math
import requests
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Abstract rates provider."""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Return normalized pair keys and numeric rates."""


class CoinGeckoClient(BaseApiClient):
    """Fetch configured cryptocurrency prices in USD."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        ids = ",".join(self.config.CRYPTO_ID_MAP.values())
        try:
            response = requests.get(self.config.COINGECKO_URL, params={"ids": ids, "vs_currencies": self.config.BASE_CURRENCY.lower()}, timeout=self.config.REQUEST_TIMEOUT)
            if response.status_code == 429:
                raise ApiRequestError("CoinGecko: превышен лимит запросов (HTTP 429)")
            if response.status_code >= 400:
                raise ApiRequestError(f"CoinGecko вернул HTTP {response.status_code}")
            payload = response.json()
            result = {}
            for code, raw_id in self.config.CRYPTO_ID_MAP.items():
                value = payload.get(raw_id, {}).get(self.config.BASE_CURRENCY.lower())
                if isinstance(value, (int, float)) and (not isinstance(value, bool)) and math.isfinite(value) and (value > 0):
                    result[f"{code}_{self.config.BASE_CURRENCY}"] = float(value)
            if not result:
                raise ApiRequestError("CoinGecko не вернул корректные курсы")
            return result
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise ApiRequestError(f"CoinGecko: {exc}") from exc


class ExchangeRateApiClient(BaseApiClient):
    """Fetch fiat rates and normalize them to USD pair keys."""

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()

    def fetch_rates(self) -> dict[str, float]:
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("не задан EXCHANGERATE_API_KEY")
        url = f"{self.config.EXCHANGERATE_API_URL}/{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
            if response.status_code == 429:
                raise ApiRequestError("ExchangeRate-API: превышен лимит запросов (HTTP 429)")
            if response.status_code in (401, 403):
                raise ApiRequestError("ExchangeRate-API: неверный или недействительный API-ключ")
            if response.status_code >= 400:
                raise ApiRequestError(f"ExchangeRate-API вернул HTTP {response.status_code}")
            payload = response.json()
            if payload.get("result") != "success":
                raise ApiRequestError(str(payload.get("error-type", "неизвестная ошибка API")))
            rates = payload.get("conversion_rates", payload.get("rates", {}))
            result = {}
            for code in self.config.FIAT_CURRENCIES:
                value = rates.get(code)
                if isinstance(value, (int, float)) and (not isinstance(value, bool)) and math.isfinite(value) and (value > 0):
                    result[f"{code}_{self.config.BASE_CURRENCY}"] = 1 / float(value)
            if not result:
                raise ApiRequestError("ExchangeRate-API не вернул корректные курсы")
            return result
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise ApiRequestError(f"ExchangeRate-API: {exc}") from exc
