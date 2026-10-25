"""Application use cases; CLI delegates business logic here."""

from datetime import UTC, datetime
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import pair_rate, validate_amount
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


class UseCases:
    """Business operations backed by JSON storage."""

    def __init__(self, database: DatabaseManager | None = None):
        self.db = database or DatabaseManager()
        self.settings = SettingsLoader()
        self.current_user: User | None = None

    def _users(self) -> list[dict]:
        return self.db.read("users.json", [])

    def _portfolios(self) -> list[dict]:
        return self.db.read("portfolios.json", [])

    def _rates(self) -> dict:
        return self.db.read("rates.json", {"pairs": {}, "last_refresh": None})

    def register(self, username: str, password: str) -> User:
        if not username or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        users = self._users()
        if any(item["username"].casefold() == username.casefold() for item in users):
            raise ValueError(f"Имя пользователя '{username}' уже занято")
        user_id = max((item["user_id"] for item in users), default=0) + 1
        user = User(user_id, username.strip(), password=password)
        users.append(user.to_dict())
        self.db.write("users.json", users)
        portfolios = self._portfolios()
        portfolios.append({"user_id": user_id, "wallets": {}})
        self.db.write("portfolios.json", portfolios)
        return user

    def login(self, username: str, password: str) -> User:
        for item in self._users():
            if item["username"].casefold() == username.casefold():
                user = User(item["user_id"], item["username"], item["hashed_password"], item["salt"], item["registration_date"])
                if not user.verify_password(password):
                    raise ValueError("Неверный пароль")
                self.current_user = user
                return user
        raise ValueError(f"Пользователь '{username}' не найден")

    def _require_login(self) -> User:
        if self.current_user is None:
            raise PermissionError("Сначала выполните login")
        return self.current_user

    def _portfolio(self, user_id: int | None = None) -> Portfolio:
        user = self._require_login()
        target_id = user.user_id if user_id is None else user_id
        if target_id != user.user_id:
            raise PermissionError("Нельзя обращаться к чужому портфелю")
        data = next((p for p in self._portfolios() if p["user_id"] == target_id), None)
        if data is None:
            data = {"user_id": target_id, "wallets": {}}
        wallets = {code: Wallet(code, item.get("balance", 0.0)) for code, item in data.get("wallets", {}).items()}
        return Portfolio(target_id, wallets, user)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        portfolios = self._portfolios()
        serialized = {"user_id": portfolio.user_id, "wallets": {code: {"currency_code": code, "balance": wallet.balance} for code, wallet in portfolio.wallets.items()}}
        for index, item in enumerate(portfolios):
            if item["user_id"] == portfolio.user_id:
                portfolios[index] = serialized
                break
        else:
            portfolios.append(serialized)
        self.db.write("portfolios.json", portfolios)

    def _get_rate(self, from_code: str, to_code: str, refresh: bool = True) -> tuple[float, str]:
        get_currency(from_code)
        get_currency(to_code)
        cache = self._rates()
        try:
            rate = pair_rate(cache, from_code, to_code)
            updated = cache.get("pairs", {}).get(f"{from_code}_{to_code}", {}).get("updated_at")
            if not updated and from_code != to_code:
                updated = cache.get("pairs", {}).get(f"{to_code}_{from_code}", {}).get("updated_at")
            if updated:
                stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=UTC)
                age = (datetime.now(UTC) - stamp).total_seconds()
                if age > int(self.settings.get("rates_ttl_seconds", 300)):
                    if refresh:
                        self._refresh_rates()
                        return self._get_rate(from_code, to_code, refresh=False)
                    raise ApiRequestError(f"Курс {from_code}→{to_code} устарел; обновление не удалось")
            elif from_code != to_code:
                if refresh:
                    self._refresh_rates()
                    return self._get_rate(from_code, to_code, refresh=False)
                raise ApiRequestError(f"Для курса {from_code}→{to_code} отсутствует время обновления")
            return (rate, updated or "unknown")
        except ApiRequestError:
            raise
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            if refresh:
                self._refresh_rates()
                try:
                    return self._get_rate(from_code, to_code, refresh=False)
                except (ApiRequestError, KeyError, ValueError, TypeError, ZeroDivisionError):
                    pass
            raise ApiRequestError(f"Курс {from_code}→{to_code} недоступен") from exc

    def _refresh_rates(self) -> None:
        from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
        from valutatrade_hub.parser_service.updater import RatesUpdater

        try:
            RatesUpdater([CoinGeckoClient(), ExchangeRateApiClient()]).run_update()
        except ApiRequestError:
            return

    @log_action("DEPOSIT", verbose=True)
    def deposit(self, user_id: int, amount: float) -> dict:
        """Add simulated funds to the user's USD wallet."""
        self._require_login()
        amount = validate_amount(amount)
        portfolio = self._portfolio(user_id)
        wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
        before = wallet.balance
        wallet.deposit(amount)
        self._save_portfolio(portfolio)
        return {"currency": "USD", "amount": amount, "before": before, "after": wallet.balance}

    @log_action("BUY", verbose=True)
    def buy(self, user_id: int, currency_code: str, amount: float) -> dict:
        self._require_login()
        amount = validate_amount(amount)
        code = currency_code.upper()
        get_currency(code)
        if code == "USD":
            raise ValueError("Покупка USD не поддерживается; используйте другой код валюты")
        rate, updated = self._get_rate(code, "USD")
        portfolio = self._portfolio(user_id)
        usd = portfolio.get_wallet("USD")
        if usd is None:
            usd = portfolio.add_currency("USD")
        cost = amount * rate
        usd.withdraw(cost)
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            wallet = portfolio.add_currency(code)
        wallet.deposit(amount)
        self._save_portfolio(portfolio)
        return {"currency": code, "amount": amount, "rate": rate, "cost": cost, "updated_at": updated}

    @log_action("SELL", verbose=True)
    def sell(self, user_id: int, currency_code: str, amount: float) -> dict:
        self._require_login()
        amount = validate_amount(amount)
        code = currency_code.upper()
        get_currency(code)
        if code == "USD":
            raise ValueError("Продажа USD не поддерживается; используйте другой код валюты")
        portfolio = self._portfolio(user_id)
        wallet = portfolio.get_wallet(code)
        if wallet is None:
            raise ValueError(f"У вас нет кошелька '{code}'. Добавьте валюту: она создаётся автоматически при первой покупке.")
        rate, updated = self._get_rate(code, "USD")
        wallet.withdraw(amount)
        usd = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
        revenue = amount * rate
        usd.deposit(revenue)
        self._save_portfolio(portfolio)
        return {"currency": code, "amount": amount, "rate": rate, "revenue": revenue, "updated_at": updated}

    def get_rate(self, from_code: str, to_code: str) -> dict:
        rate, updated = self._get_rate(from_code.upper(), to_code.upper())
        return {"from": from_code.upper(), "to": to_code.upper(), "rate": rate, "updated_at": updated}

    def show_portfolio(self, base_currency: str = "USD") -> dict:
        portfolio = self._portfolio()
        get_currency(base_currency.upper())
        cache = self._rates()
        pairs = cache.get("pairs", {})
        rates = {key: float(value["rate"] if isinstance(value, dict) else value) for key, value in pairs.items()}
        return {"portfolio": portfolio, "base": base_currency.upper(), "total": portfolio.get_total_value(base_currency.upper(), rates)}
