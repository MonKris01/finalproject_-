"""Domain-specific exceptions."""


class InsufficientFundsError(Exception):
    """Raised when a wallet does not have enough funds."""

    def __init__(self, available: float, required: float, code: str):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(f"Недостаточно средств: доступно {available:.4f} {code}, требуется {required:.4f} {code}")


class CurrencyNotFoundError(Exception):
    """Raised when a currency code is not registered."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """Raised when an external rates API cannot provide valid data."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
