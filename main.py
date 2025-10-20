#!/usr/bin/env python
import logging
import time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.market.jobs import trading_logic, update_bonds

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    update_bonds_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour="10-18",
        timezone=ZoneInfo("Europe/Moscow"),
    )

    trading_logic_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour="10-18",
        minute="*/5",
        timezone=ZoneInfo("Europe/Moscow"),
    )

    logging.info("Performing initial bond data load...")
    update_bonds()
    logging.info("Initial bond data load complete.")

    scheduler.add_job(update_bonds, update_bonds_trigger)
    scheduler.add_job(trading_logic, trading_logic_trigger)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
