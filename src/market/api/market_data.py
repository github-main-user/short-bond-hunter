import logging
from datetime import datetime, timedelta, timezone

from t_tech.invest import CandleInterval
from t_tech.invest.async_services import AsyncServices

from src.market.utils import normalize_quotation

logger = logging.getLogger(__name__)

_TMON_FIGI = "TCS70A106DL2"


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
        response = await client.market_data.get_last_prices(figi=[_TMON_FIGI])
        if not response.last_prices:
            logger.warning(f"Can't fetch TMON@ last price at {target_time}")
            return None
        return normalize_quotation(response.last_prices[0].price)

    day_start = target_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(hours=23, minutes=59, seconds=59)
    response = await client.market_data.get_candles(
        figi=_TMON_FIGI,
        from_=day_start,
        to=day_end,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
    )
    if not response.candles:
        logger.warning(
            f"Can't fetch TMON@ price at {target_time}: no candles available"
        )
        return None
    candle = response.candles[0]
    return (normalize_quotation(candle.open) + normalize_quotation(candle.close)) / 2
