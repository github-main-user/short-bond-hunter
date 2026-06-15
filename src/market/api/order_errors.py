import logging
from enum import Enum, auto

from t_tech.invest import AioRequestError

logger = logging.getLogger(__name__)


class OrderErrorAction(Enum):
    HANDLED = auto()
    RERAISE = auto()


_INSTRUMENT_NOT_TRADABLE = "30079"
_ORDER_ALREADY_EXECUTED = "30059"

_HANDLED_CODES = {_INSTRUMENT_NOT_TRADABLE, _ORDER_ALREADY_EXECUTED}


def extract_order_error(e: AioRequestError) -> tuple[str, str]:
    code = (e.details or "").partition(":")[0].strip()
    message = e.metadata.message if e.metadata else ""
    return code, message


def classify_order_error(e: AioRequestError) -> OrderErrorAction:
    code, _ = extract_order_error(e)
    if code in _HANDLED_CODES:
        return OrderErrorAction.HANDLED
    return OrderErrorAction.RERAISE


def handle_order_error(e: AioRequestError, context: str) -> None:
    if classify_order_error(e) is OrderErrorAction.RERAISE:
        raise e
    code, message = extract_order_error(e)
    logger.warning(f"{context} skipped: broker error {code} ({message})")
