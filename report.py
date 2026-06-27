#!/usr/bin/env python
import argparse

import structlog

from src.log_setup import setup_logging
from src.stats import generate_report

log = structlog.get_logger(__name__)

GROUPS = ("purchase", "month", "bond")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=GROUPS)
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()

    setup_logging()
    log.info("report_generating", group=args.group, plot=args.plot)
    generate_report(group=args.group, plot=args.plot)


if __name__ == "__main__":
    main()
