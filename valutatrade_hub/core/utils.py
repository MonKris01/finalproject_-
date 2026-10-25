"""Currency validation and exchange-rate conversion helpers."""


def validate_amount(amount: float) -> float:
    """Validate a positive finite amount."""
    import math

    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or (not math.isfinite(amount)) or (amount <= 0):
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


def pair_rate(rates: dict, from_code: str, to_code: str) -> float:
    """Resolve a direct or inverse currency pair from a rates cache."""
    if from_code == to_code:
        return 1.0
    pairs = rates.get("pairs", rates)
    direct = pairs.get(f"{from_code}_{to_code}")
    if isinstance(direct, dict):
        direct = direct.get("rate")
    if direct is not None:
        return float(direct)
    inverse = pairs.get(f"{to_code}_{from_code}")
    if isinstance(inverse, dict):
        inverse = inverse.get("rate")
    if inverse is not None and float(inverse) != 0:
        return 1 / float(inverse)
    usd_from = pairs.get(f"{from_code}_USD")
    usd_to = pairs.get(f"{to_code}_USD")
    if isinstance(usd_from, dict):
        usd_from = usd_from.get("rate")
    if isinstance(usd_to, dict):
        usd_to = usd_to.get("rate")
    if usd_from is not None and usd_to:
        return float(usd_from) / float(usd_to)
    raise KeyError(f"Курс {from_code}→{to_code} недоступен")
