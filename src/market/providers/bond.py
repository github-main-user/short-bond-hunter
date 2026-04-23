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

from src.config import Settings
from src.market.domain import EnrichedBond
from src.market.services import get_tradable_bonds

logger = logging.getLogger(__name__)


class BondProvider:
    def __init__(self, token: str, settings: Settings) -> None:
        self._token = token
        self._settings = settings

    async def stream(self):
        while True:
            async with AsyncClient(self._token) as client:
                bonds = await get_tradable_bonds(client)
                async for bond in self._stream_price_updates(client, bonds):
                    yield bond

    async def _stream_price_updates(
        self, client: AsyncServices, bonds: list[EnrichedBond]
    ):
        figi_to_bond = {b.figi: b for b in bonds}

        async def request_iterator():
            yield MarketDataRequest(
                subscribe_order_book_request=SubscribeOrderBookRequest(
                    subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                    instruments=[
                        OrderBookInstrument(figi=b.figi, depth=1) for b in bonds
                    ],
                )
            )
            while True:
                await asyncio.sleep(1)

        logger.info(f"Subscribed to {len(bonds)} bonds")

        try:
            async with asyncio.timeout(self._settings.BOND_REFRESH_INTERVAL_SECONDS):
                async for marketdata in client.market_data_stream.market_data_stream(
                    request_iterator()
                ):
                    if not marketdata.orderbook:
                        logger.info("Skipped market data: no orderbook")
                        continue

                    bond = figi_to_bond.get(marketdata.orderbook.figi)
                    if not bond:
                        logger.debug(
                            f"Skipped update for bond {marketdata.orderbook.figi} (figi):"
                            " not in the list"
                        )
                        continue

                    old_price = bond.real_price
                    bond.update(marketdata.orderbook)

                    if old_price != bond.real_price:
                        yield bond
        except TimeoutError:
            logger.info("Bonds update interval reached. Re-fetching...")
