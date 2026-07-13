#!/usr/bin/env python
import asyncio
import os

import structlog

from src.log_setup import setup_logging
from src.market import start_market_session

log = structlog.get_logger(__name__)


def main() -> None:
    os.environ.setdefault("SSL_TBANK_VERIFY", "true")

    setup_logging()
    log.info("market_session_started")

    try:
        asyncio.run(start_market_session())
    except KeyboardInterrupt:
        pass

    log.info("market_session_stopped")


if __name__ == "__main__":
    main()
