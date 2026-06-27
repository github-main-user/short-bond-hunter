#!/usr/bin/env python
import asyncio
import logging
import os

from src.log_setup import setup_logging
from src.market import start_market_session


def main() -> None:
    os.environ.setdefault("SSL_TBANK_VERIFY", "true")

    setup_logging()
    logging.info("Starting market streaming session")

    try:
        asyncio.run(start_market_session())
    except KeyboardInterrupt:
        pass

    logging.info("Ending market streaming session")


if __name__ == "__main__":
    main()
