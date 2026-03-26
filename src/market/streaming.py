import asyncio
import logging

from t_tech.invest import (
    AsyncClient,
    MarketDataRequest,
    OrderBookInstrument,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from t_tech.invest.async_services import AsyncServices

from src.config import settings
from src.market.api import fetch_account_id
from src.market.maturity import check_missed_maturities, start_maturity_stream_session
from src.market.purchase import process_bond_for_purchase
from src.market.schemas import NBond
from src.market.services import get_tradable_bonds
from src.stats.repository import StatsRepository

logger = logging.getLogger(__name__)


async def _handle_market_data_stream(
    client: AsyncServices, bonds: list[NBond], stats_repo: StatsRepository
) -> None:
    figi_to_bond_map = {b.figi: b for b in bonds}
    account_id = await fetch_account_id(client)

    async def request_iterator():
        yield MarketDataRequest(
            subscribe_order_book_request=SubscribeOrderBookRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[OrderBookInstrument(figi=b.figi, depth=1) for b in bonds],
            )
        )
        while True:
            await asyncio.sleep(1)

    logger.info(f"Subscribed to {len(bonds)} bonds")

    async def stream_processor():
        async for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if not marketdata.orderbook:
                logger.info("Skipped market data: no orderbook")
                continue

            bond = figi_to_bond_map.get(marketdata.orderbook.figi)
            if not bond:
                logger.debug(
                    f"Skipped update for bond {marketdata.orderbook.figi} "
                    "(figi): not in the list"
                )
                continue

            old_price = bond.real_price
            bond.orderbook = marketdata.orderbook

            # if price changed
            if old_price != bond.real_price:
                await process_bond_for_purchase(client, bond, stats_repo, account_id)

    processor_task = asyncio.create_task(stream_processor())

    try:
        await asyncio.wait_for(
            processor_task, timeout=settings.BOND_REFRESH_INTERVAL_SECONDS
        )
    except asyncio.TimeoutError:
        logger.info("Bonds update interval reached. Re-fetching...")
    finally:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            logger.debug("Market data stream processing task cancelled.")


async def start_market_streaming_session() -> None:
    stats_repo = StatsRepository()

    async def _market_data_loop() -> None:
        while True:
            try:
                async with AsyncClient(settings.TINVEST_TOKEN) as client:
                    bonds = await get_tradable_bonds(client)
                    await _handle_market_data_stream(client, bonds, stats_repo)
            except Exception as e:
                logger.error(f"Unexpected error in the main session loop: {e}")
                logger.info("Retrying in 5 minutes...")
                await asyncio.sleep(60 * 5)

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)
        await check_missed_maturities(client, account_id, stats_repo)

    await asyncio.gather(
        _market_data_loop(),
        start_maturity_stream_session(account_id, stats_repo),
    )
