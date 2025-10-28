import asyncio
import logging

from tinkoff.invest import (
    AsyncClient,
    MarketDataRequest,
    OrderBookInstrument,
    RequestError,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from tinkoff.invest.async_services import AsyncServices

from src.config import settings
from src.market.processing import process_bond_for_purchase
from src.market.schemas import NBond
from src.market.services import fetch_bonds, fetch_coupons_sum
from src.market.utils import filter_bonds

logger = logging.getLogger(__name__)


async def get_tradable_bonds(client: AsyncServices) -> list[NBond]:
    """
    Fetches and prepares a list of tradable bonds.
    """
    bonds = await fetch_bonds(client)
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    coupon_sums = await asyncio.gather(
        *[fetch_coupons_sum(client, bond) for bond in bonds]
    )
    for bond, coupon_sum in zip(bonds, coupon_sums):
        bond.coupons_sum = coupon_sum

    return bonds


async def _handle_market_data_stream(client: AsyncServices, bonds: list[NBond]) -> None:
    """
    Handles the market data stream for a list of bonds.
    """
    figi_to_bond_map = {b.figi: b for b in bonds}

    async def request_iterator():
        yield MarketDataRequest(
            subscribe_order_book_request=SubscribeOrderBookRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[OrderBookInstrument(figi=b.figi, depth=1) for b in bonds],
            )
        )
        while True:
            await asyncio.sleep(1)

    logger.info(f"Subscribed to %s bonds", len(bonds))

    loop = asyncio.get_event_loop()
    last_update_time = loop.time()
    try:
        async for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if loop.time() - last_update_time > settings.BOND_REFRESH_INTERVAL_SECONDS:
                logger.info("Bonds update interval reached. Re-fetching...")
                break

            if not marketdata.orderbook:
                logger.info("Skipped marketdata - Got no orderbook")
                continue

            bond = figi_to_bond_map.get(marketdata.orderbook.figi)
            if not bond:
                logger.debug(
                    "Skipped update for bond %s (figi) - Not in the list",
                    marketdata.orderbook.figi,
                )
                continue

            old_price = bond.real_price
            bond.orderbook = marketdata.orderbook

            # if price changed
            if old_price != bond.real_price:
                await process_bond_for_purchase(client, bond)
    except RequestError as e:
        logger.error("Error during market data stream: %s", e)


async def start_market_streaming_session() -> None:
    """
    Starts the main market streaming session.
    """
    while True:
        async with AsyncClient(settings.TINVEST_TOKEN) as client:
            bonds = await get_tradable_bonds(client)
            await _handle_market_data_stream(client, bonds)
