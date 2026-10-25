"""Domain models for users, wallets and portfolios."""

import hashlib
import math
import secrets
from datetime import datetime
from typing import Any
from valutatrade_hub.core.exceptions import InsufficientFundsError


class User:
    """Registered user with salted password hash."""

    def __init__(self, user_id: int, username: str, hashed_password: str = "", salt: str = "", registration_date: datetime | str | None = None, password: str | None = None):
        self._user_id = int(user_id)
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = username.strip()
        self._salt = salt or secrets.token_hex(16)
        self._hashed_password = hashed_password
        self._registration_date = datetime.fromisoformat(registration_date) if isinstance(registration_date, str) else registration_date or datetime.now()
        if password is not None:
            self.change_password(password)
        elif not self._hashed_password:
            raise ValueError("Необходимо передать пароль или его хеш")

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    def change_password(self, new_password: str) -> None:
        """Hash a new password using this user's unique salt."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._hashed_password = hashlib.sha256((new_password + self._salt).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Check a password without exposing the stored hash."""
        candidate = hashlib.sha256((password + self._salt).encode("utf-8")).hexdigest()
        return secrets.compare_digest(candidate, self._hashed_password)

    def get_user_info(self) -> dict[str, Any]:
        """Return public user details, excluding password and salt."""
        return {"user_id": self._user_id, "username": self._username, "registration_date": self._registration_date.isoformat()}

    def to_dict(self) -> dict[str, Any]:
        """Serialize user to JSON-compatible dictionary."""
        return {"user_id": self._user_id, "username": self._username, "hashed_password": self._hashed_password, "salt": self._salt, "registration_date": self._registration_date.isoformat()}


class Wallet:
    """Wallet that validates deposits, withdrawals and balance."""

    def __init__(self, currency_code: str, balance: float = 0.0):
        if not isinstance(currency_code, str) or not currency_code:
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.upper()
        self.balance = balance

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Баланс не может быть отрицательным или бесконечным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Add a positive amount to the wallet."""
        amount = self._validate_amount(amount)
        self.balance = self.balance + amount

    def withdraw(self, amount: float) -> None:
        """Withdraw funds or raise InsufficientFundsError."""
        amount = self._validate_amount(amount)
        if amount > self.balance + 1e-09:
            raise InsufficientFundsError(self.balance, amount, self.currency_code)
        self.balance = max(0.0, self.balance - amount)

    @staticmethod
    def _validate_amount(amount: float) -> float:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("'amount' должен быть числом")
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        return float(amount)

    def get_balance_info(self) -> str:
        """Format current wallet balance."""
        return f"{self.currency_code}: {self.balance:.4f}"


class Portfolio:
    """Collection of wallets owned by a user."""

    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None, user: User | None = None):
        self._user_id = int(user_id)
        self._user = user
        self._wallets = dict(wallets or {})

    @property
    def user(self) -> User | None:
        return self._user

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        return self._wallets.copy()

    def add_currency(self, currency_code: str) -> Wallet:
        """Create and return a wallet if it does not already exist."""
        code = currency_code.upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже существует")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Return a wallet by code, if present."""
        return self._wallets.get(currency_code.upper())

    def get_total_value(self, base_currency: str = "USD", exchange_rates: dict[str, float] | None = None) -> float:
        """Convert all wallet balances to a base currency."""
        rates = {"USD_USD": 1.0, "EUR_USD": 1.08, "GBP_USD": 1.25, "RUB_USD": 0.0105, "BTC_USD": 65000.0, "ETH_USD": 3200.0, "SOL_USD": 150.0} if exchange_rates is None else exchange_rates
        base = base_currency.upper()
        total = 0.0
        base_to_usd = 1.0 if base == "USD" else rates.get(f"{base}_USD")
        if base_to_usd is None or float(base_to_usd) <= 0:
            raise ValueError(f"Неизвестная базовая валюта '{base}'")
        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            if code == "USD":
                to_usd = 1.0
            else:
                to_usd = rates.get(f"{code}_USD")
            if to_usd is None or float(to_usd) <= 0:
                raise ValueError(f"Не удалось получить курс для '{code}'")
            total += wallet.balance * float(to_usd) / float(base_to_usd)
        return total
