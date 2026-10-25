"""Simple interval scheduler for Parser Service."""

import logging
import time
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.updater import RatesUpdater


def run_scheduler(updater: RatesUpdater, interval_seconds: int = 300) -> None:
    """Run updates periodically until interrupted by the operator."""
    logger = logging.getLogger("valutatrade")
    try:
        while True:
            try:
                updater.run_update()
            except ApiRequestError as exc:
                logger.error("Scheduled rates update failed: %s", exc)
            time.sleep(max(1, interval_seconds))
    except KeyboardInterrupt:
        logger.info("Parser scheduler stopped")
