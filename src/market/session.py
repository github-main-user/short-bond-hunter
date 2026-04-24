import asyncio
import logging

from src.config import settings
from src.market.api import fetch_account_id
from src.stats import StatsRepository

logger = logging.getLogger(__name__)


async def _with_retry(fn, *args, **kwargs) -> None:
    while True:
        try:
            await fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unexpected error in {fn.__name__}: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)


async def start_market_streaming_session() -> None:
    stats_repo = StatsRepository()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)
