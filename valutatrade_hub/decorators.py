"""Domain-operation logging decorators."""

import functools
import logging
from datetime import UTC, datetime


def log_action(action: str | None = None, verbose: bool = False):
    """Log successful and failed operations without swallowing exceptions."""

    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger("valutatrade")
            label = (action or func.__name__).upper()
            signature = __import__("inspect").signature(func)
            try:
                bound = signature.bind_partial(*args, **kwargs)
                arguments = bound.arguments
            except TypeError:
                arguments = kwargs
            instance = args[0] if args else None
            current_user = getattr(instance, "current_user", None)
            username = arguments.get("username", getattr(current_user, "username", arguments.get("user_id", "unknown")))
            currency = arguments.get("currency_code", arguments.get("currency", "USD" if label == "DEPOSIT" else "-"))
            amount = arguments.get("amount", "-")
            try:
                result = func(*args, **kwargs)
                details = " result=OK"
                if isinstance(result, dict):
                    details += f" rate={result.get('rate', '-')} base='USD'"
                if verbose:
                    details += f" details={result!r}"
                logger.info("%s action=%s user=%r currency=%r amount=%r%s", datetime.now(UTC).isoformat(), label, username, currency, amount, details)
                return result
            except Exception as exc:
                logger.info("%s action=%s user=%r currency=%r amount=%r result=ERROR error_type=%s error_message=%r", datetime.now(UTC).isoformat(), label, username, currency, amount, type(exc).__name__, str(exc))
                raise

        return wrapper

    return decorator
