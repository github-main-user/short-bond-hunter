#!/usr/bin/env python
import asyncio
import logging

from src.logging import setup_logging
from src.market import start_market_session


def main() -> None:
    setup_logging()
    logging.info("Starting market streaming session")

    try:
        asyncio.run(start_market_session())
    except KeyboardInterrupt:
        pass

    logging.info("Ending market streaming session")


if __name__ == "__main__":
    main()
