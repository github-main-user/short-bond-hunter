import logging
from datetime import datetime, timedelta

from t_tech.invest import CandleInterval
from t_tech.invest.async_services import AsyncServices

from src.market.utils import normalize_quotation

logger = logging.getLogger(__name__)

_TMON_FIGI = "TCS70A106DL2"


async def fetch_tmon_etf_price_at(
    client: AsyncServices, target_time: datetime
) -> float | None:
    response = await client.market_data.get_candles(
        figi=_TMON_FIGI,
        from_=target_time - timedelta(days=3),  # type: ignore
        to=target_time,
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
    )
    if not response.candles:
        logger.warning(
            f"Can't fetch TMON@ price at {target_time}: no candles available"
        )
        return None
    return normalize_quotation(response.candles[-1].close)
