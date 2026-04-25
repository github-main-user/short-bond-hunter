import asyncio
import logging

from t_tech.invest import AsyncClient

from src.config import settings
from src.market.api import fetch_account_id
from src.market.pipeline import process_bond, process_maturity
from src.market.providers import (
    BondProvider,
    DailyMissedMaturityProvider,
    RealtimeMaturityProvider,
)
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


async def start_market_session() -> None:
    stats_repo = StatsRepository()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)

        async def bond_loop():
            async for bond in BondProvider(settings).stream():
                await process_bond(client, bond, stats_repo, account_id)

        async def maturity_loop():
            async for event in RealtimeMaturityProvider(account_id, settings).stream():
                await process_maturity(client, stats_repo, event)

        async def missed_loop():
            async for event in DailyMissedMaturityProvider(
                account_id, settings
            ).stream():
                await process_maturity(client, stats_repo, event)

        await asyncio.gather(
            _with_retry(bond_loop),
            _with_retry(maturity_loop),
            _with_retry(missed_loop),
        )
