"""Background worker: runs the full pipeline on a loop.

Started as its own process/container in production. It waits briefly at boot
(so the web service can apply DB migrations first), then repeatedly runs
ingest → cluster → rank → synthesize, sleeping `INGEST_POLL_INTERVAL_SECONDS`
between cycles.
"""
from __future__ import annotations

import time

from app.core.config import settings
from app.core.logging import get_logger
from app.tasks.scheduler import run_full_cycle

logger = get_logger("worker")


def main() -> None:
    logger.info("worker starting; interval=%ss", settings.ingest_poll_interval_seconds)
    time.sleep(15)  # let the web service run migrations first
    while True:
        try:
            run_full_cycle()
        except Exception as exc:  # keep the loop alive on any failure
            logger.warning("cycle failed: %s", exc)
        time.sleep(settings.ingest_poll_interval_seconds)


if __name__ == "__main__":
    main()
