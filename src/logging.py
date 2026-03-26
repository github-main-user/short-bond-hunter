import logging
from datetime import datetime, timedelta, timezone


class _TzFormatter(logging.Formatter):
    _tz = timezone(timedelta(hours=3))

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def setup_logging():
    formatter = _TzFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log"),
        logging.FileHandler("logs/latest.log", mode="w"),
    ]
    for h in handlers:
        h.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=handlers)
