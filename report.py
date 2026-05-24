#!/usr/bin/env python
import logging

from src.logging import setup_logging
from src.stats import generate_statistics, init_db


def main() -> None:
    setup_logging()
    init_db()
    logging.info("Generating statistics...")
    generate_statistics()


if __name__ == "__main__":
    main()
