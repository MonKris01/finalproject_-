"""Singleton settings loader."""

import tomllib
from pathlib import Path
from typing import Any


class SettingsLoader:
    """Load project configuration once; __new__ keeps one readable instance."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._config: dict[str, Any] = {"data_dir": "data", "rates_ttl_seconds": 300, "base_currency": "USD", "log_file": "logs/actions.log", "log_level": "INFO"}
        config_path = Path("pyproject.toml")
        if config_path.exists():
            try:
                with config_path.open("rb") as file:
                    parsed = tomllib.load(file)
                self._config.update(parsed.get("tool", {}).get("valutatrade", {}))
            except (OSError, tomllib.TOMLDecodeError):
                pass
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._loaded = False
        self.__init__()
