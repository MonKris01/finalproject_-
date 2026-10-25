"""Atomic storage for latest rates and historical measurements."""

from datetime import UTC, datetime
from valutatrade_hub.infra.database import DatabaseManager


class RatesStorage:
    """Persist current rates and append unique historical observations."""

    def __init__(self, database: DatabaseManager | None = None):
        self.database = database or DatabaseManager()

    def save(self, rates: dict[str, float], sources: dict[str, str] | None = None) -> int:
        now = datetime.now(UTC).isoformat()
        current = self.database.read("rates.json", {"pairs": {}, "last_refresh": None})
        pairs = current.setdefault("pairs", {})
        history = self.database.read("exchange_rates.json", [])
        existing_ids = {item.get("id") for item in history if isinstance(item, dict)}
        added = 0
        for pair, rate in rates.items():
            if not isinstance(rate, (int, float)) or rate <= 0:
                continue
            from_code, to_code = pair.split("_", 1)
            source = (sources or {}).get(pair, "ParserService")
            old = pairs.get(pair, {})
            old_timestamp = old.get("updated_at")
            is_newer = True
            if old_timestamp:
                try:
                    old_time = datetime.fromisoformat(old_timestamp.replace("Z", "+00:00"))
                    if old_time.tzinfo is None:
                        old_time = old_time.replace(tzinfo=UTC)
                    new_time = datetime.fromisoformat(now)
                    is_newer = new_time > old_time
                except (AttributeError, TypeError, ValueError):
                    is_newer = True
            if is_newer:
                pairs[pair] = {"rate": float(rate), "updated_at": now, "source": source}
            record_id = f"{from_code}_{to_code}_{now}"
            if record_id not in existing_ids:
                history.append({"id": record_id, "from_currency": from_code, "to_currency": to_code, "rate": float(rate), "timestamp": now, "source": source, "meta": {}})
                existing_ids.add(record_id)
                added += 1
        current["last_refresh"] = now
        previous_current = self.database.read("rates.json", {"pairs": {}, "last_refresh": None})
        self.database.write("rates.json", current)
        try:
            self.database.write("exchange_rates.json", history)
        except Exception:
            self.database.write("rates.json", previous_current)
            raise
        return added
