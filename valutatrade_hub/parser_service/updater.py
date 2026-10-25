"""Coordinate API clients and save their successful results."""

import logging
from datetime import UTC, datetime
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Fetch rates from all configured clients, tolerating individual failures."""

    def __init__(self, clients: list, storage: RatesStorage | None = None):
        self.clients = clients
        self.storage = storage or RatesStorage()
        self.logger = logging.getLogger("valutatrade")

    def run_update(self, source: str | None = None) -> dict:
        self.logger.info("Starting rates update...")
        if source is not None and source.lower() not in {"coingecko", "exchangerate"}:
            raise ValueError("Источник должен быть coingecko или exchangerate")
        combined: dict[str, float] = {}
        sources: dict[str, str] = {}
        errors = []
        for client in self.clients:
            name = client.__class__.__name__
            if source and source.lower() not in name.lower():
                continue
            try:
                rates = client.fetch_rates()
                combined.update(rates)
                source_name = "CoinGecko" if "CoinGecko" in name else "ExchangeRate-API"
                sources.update({pair: source_name for pair in rates})
                self.logger.info("Fetching from %s... OK (%s rates)", source_name, len(rates))
            except Exception as exc:
                errors.append(str(exc))
                self.logger.exception("Failed to fetch from %s: %s", name, exc)
        if combined:
            count = self.storage.save(combined, sources)
            self.logger.info("Writing %s rates to data/rates.json...", count)
        if errors and (not combined):
            raise ApiRequestError("; ".join(errors))
        return {"updated": len(combined), "last_refresh": datetime.now(UTC).isoformat(), "errors": errors}
