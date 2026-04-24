#!/usr/bin/env python
import argparse
import asyncio
import logging

from src.logging import setup_logging
from src.market import start_market_session
from src.stats import generate_statistics, init_db


def main(args: argparse.Namespace) -> None:
    setup_logging()
    init_db()

    if args.display_statistics:
        logging.info("Generating statistics...")
        generate_statistics()
        return

    logging.info("Starting market streaming session")

    try:
        asyncio.run(start_market_session())
    except KeyboardInterrupt:
        pass

    logging.info("Ending market streaming session")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--display-statistics", action="store_true")

    main(parser.parse_args())
