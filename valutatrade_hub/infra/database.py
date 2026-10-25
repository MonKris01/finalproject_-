"""Atomic JSON database manager implemented as a Singleton."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Read and write JSON files atomically through a single manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def path(self, filename: str) -> Path:
        return Path(SettingsLoader().get("data_dir", "data")) / filename

    def read(self, filename: str, default: Any) -> Any:
        path = self.path(filename)
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return default
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Не удалось прочитать {path}: {exc}") from exc

    def write(self, filename: str, data: Any) -> None:
        path = self.path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
