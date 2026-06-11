import logging
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler


class _TzFormatter(logging.Formatter):
    _tz = timezone(timedelta(hours=3))

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self._tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def setup_logging():
    formatter = _TzFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler(
        "logs/app.log", when="midnight", backupCount=14
    )
    file_handler.setLevel(logging.DEBUG)

    handlers: list[logging.Handler] = [stream_handler, file_handler]
    for h in handlers:
        h.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=handlers)
    logging.getLogger("t_tech").setLevel(logging.WARNING)
    for noisy in ("grpc", "asyncio", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.INFO)
