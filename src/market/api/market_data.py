import structlog
from datetime import datetime, timedelta, timezone

from t_tech.invest.grpc.schemas import (
    CandleInterval,
    GetCandlesRequest,
    GetLastPricesRequest,
    GetOrderBookRequest,
    OrderBook,
)
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.market.utils import to_float

log = structlog.get_logger(__name__)

_TMON_FIGI = "TCS70A106DL2"


async def fetch_orderbook(
    client: AsyncServices, figi: str, depth: int = 1
) -> OrderBook:
    response = await client.market_data.get_order_book(
        request=GetOrderBookRequest(figi=figi, depth=depth)
    )
    return OrderBook(figi=figi, asks=response.asks, bids=response.bids)


async def fetch_tmon_etf_price_at(
    client: AsyncServices, target_time: datetime
) -> float | None:
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    else:
        target_time = target_time.astimezone(timezone.utc)
    now = datetime.now(tz=timezone.utc)
    is_today = target_time.date() == now.date()

    if is_today:
        response = await client.market_data.get_last_prices(
            request=GetLastPricesRequest(figi=[_TMON_FIGI])
        )
        if not response.last_prices:
            log.warning(
                "tmon_price_fetch_failed",
                target_time=target_time.isoformat(),
                reason="no_last_prices",
            )
            return None
        return to_float(response.last_prices[0].price)

    day_start = target_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(hours=23, minutes=59, seconds=59)
    response = await client.market_data.get_candles(
        request=GetCandlesRequest(
            figi=_TMON_FIGI,
            from_=day_start,
            to=day_end,
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        )
    )
    if not response.candles:
        log.warning(
            "tmon_price_fetch_failed",
            target_time=target_time.isoformat(),
            reason="no_candles",
        )
        return None
    candle = response.candles[0]
    return (to_float(candle.open) + to_float(candle.close)) / 2
