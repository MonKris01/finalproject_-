"""Logging configuration with rotating human-readable log files."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from valutatrade_hub.infra.settings import SettingsLoader


def configure_logging() -> logging.Logger:
    """Configure INFO logging and size-based rotation."""
    settings = SettingsLoader()
    path = Path(settings.get("log_file", "logs/actions.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("valutatrade")
    logger.setLevel(getattr(logging, settings.get("log_level", "INFO").upper(), logging.INFO))
    if not logger.handlers:
        formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s", "%Y-%m-%dT%H:%M:%S")
        handler = RotatingFileHandler(path, maxBytes=1000000, backupCount=3, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    return logger
