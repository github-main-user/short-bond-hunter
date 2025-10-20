#!/usr/bin/env python
import logging
import time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.logic import logic

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    trigger = CronTrigger(
        day_of_week="mon-sat",
        hour="10-18",
        minute="*/15",
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(logic, trigger)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
