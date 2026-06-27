import structlog

from t_tech.invest.exceptions import AioRequestError

log = structlog.get_logger(__name__)


_INSTRUMENT_NOT_TRADABLE = "30079"
_ORDER_ALREADY_EXECUTED = "30059"

_HANDLED_CODES = {_INSTRUMENT_NOT_TRADABLE, _ORDER_ALREADY_EXECUTED}


def handle_order_error(
    e: AioRequestError,
    *,
    operation: str,
    figi: str,
    ticker: str,
    order_id: str | None = None,
) -> None:
    code = (e.details or "").partition(":")[0].strip()
    if code not in _HANDLED_CODES:
        raise e
    message = e.metadata.message if e.metadata else ""
    log.warning(
        "broker_order_error_handled",
        operation=operation,
        figi=figi,
        ticker=ticker,
        order_id=order_id,
        code=code,
        message=message,
    )
