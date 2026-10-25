"""Currency hierarchy and registry."""

from abc import ABC, abstractmethod
from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Abstract currency representation."""

    def __init__(self, name: str, code: str):
        if not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if not (2 <= len(code) <= 5 and code.isalpha() and (code == code.upper())):
            raise ValueError("Код валюты должен содержать 2–5 букв верхнего регистра")
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Return human-readable currency information."""


class FiatCurrency(Currency):
    """Fiat currency issued by a country or monetary zone."""

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        if not issuing_country.strip():
            raise ValueError("Страна/зона эмиссии не может быть пустой")
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Cryptocurrency metadata."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        super().__init__(name, code)
        if not algorithm.strip() or market_cap < 0:
            raise ValueError("Некорректные параметры криптовалюты")
        self.algorithm = algorithm
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"


_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("Pound Sterling", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1120000000000.0),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 380000000000.0),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 70000000000.0),
}


def get_currency(code: str) -> Currency:
    """Return currency metadata or raise CurrencyNotFoundError."""
    if not isinstance(code, str) or code != code.upper():
        raise CurrencyNotFoundError(str(code))
    try:
        return _CURRENCIES[code]
    except KeyError as exc:
        raise CurrencyNotFoundError(code) from exc


def supported_currencies() -> list[str]:
    """Return supported currency codes."""
    return sorted(_CURRENCIES)
