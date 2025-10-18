#!/usr/bin/env python
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from market.utils import filter_bonds
from src.market.services import fetch_bonds, update_market_data


def main() -> None:
    bonds = fetch_bonds()
    print(f"Got {len(bonds)} bonds")

    bonds = filter_bonds(bonds, maximum_days=30)
    print(f"{len(bonds)} bonds left after filtration")

    for bond in bonds:
        update_market_data(fee_percent=0.05, bond=bond)

    for bond in bonds:
        if bond.market_data and bond.market_data.annual_yield >= 20:
            pass


if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour="10-18",
        minute="*/15",
        timezone="UTC",
    )

    scheduler.add_job(main, trigger)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
