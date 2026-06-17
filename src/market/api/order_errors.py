import logging

from t_tech.invest import AioRequestError

logger = logging.getLogger(__name__)


_INSTRUMENT_NOT_TRADABLE = "30079"
_ORDER_ALREADY_EXECUTED = "30059"

_HANDLED_CODES = {_INSTRUMENT_NOT_TRADABLE, _ORDER_ALREADY_EXECUTED}


def handle_order_error(e: AioRequestError, context: str) -> None:
    code = (e.details or "").partition(":")[0].strip()
    if code not in _HANDLED_CODES:
        raise e
    message = e.metadata.message if e.metadata else ""
    logger.warning(f"{context} skipped: broker error {code} ({message})")
