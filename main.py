#!/usr/bin/env python
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.market.services import fetch_bonds, update_market_data
from src.market.utils import filter_bonds
from src.telegram.services import send_telegram_message


def main() -> None:
    bonds = fetch_bonds()
    print(f"Got {len(bonds)} bonds")

    bonds = filter_bonds(bonds, maximum_days=30)
    print(f"{len(bonds)} bonds left after filtration")

    for bond in bonds:
        try:
            update_market_data(fee_percent=0.05, bond=bond)
        except Exception as e:
            print(f"Got an exception: {e}")

    for bond in bonds:
        if bond.market_data and bond.market_data.annual_yield >= 20:
            message = f"Bond {bond.ticker} has annual yeild more then 20%"
            send_telegram_message(message)


if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    trigger = CronTrigger(
        day_of_week="mon-sat",
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
