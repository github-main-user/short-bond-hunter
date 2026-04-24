import asyncio
import logging

from t_tech.invest import (
    AsyncClient,
    MarketDataRequest,
    OrderBook,
    OrderBookInstrument,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from t_tech.invest.async_services import AsyncServices

from src.config import Settings, settings
from src.market.api import fetch_coupons_sum, fetch_raw_bonds, fetch_user_commission
from src.market.domain import EnrichedBond
from src.market.utils import filter_bonds

logger = logging.getLogger(__name__)


class BondProvider:
    def __init__(self, token: str, settings: Settings) -> None:
        self._token = token
        self._settings = settings

    async def _get_tradable_bonds(client: AsyncServices) -> list[EnrichedBond]:
        user_commission = await fetch_user_commission(client)
        raw_bonds = await fetch_raw_bonds(client)
        logger.info(f"Got {len(raw_bonds)} bonds")

        filtered = filter_bonds(raw_bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
        logger.info(f"{len(filtered)} bonds left after filtering")

        coupon_sums = await asyncio.gather(
            *[
                fetch_coupons_sum(client, bond.figi, bond.maturity_date)
                for bond in filtered
            ]
        )

        return [
            EnrichedBond.from_bond(
                bond,
                commission_percent=user_commission,
                coupons_sum=coupon_sum,
                orderbook=OrderBook(figi=bond.figi, asks=[]),
            )
            for bond, coupon_sum in zip(filtered, coupon_sums)
        ]

    async def stream(self):
        while True:
            async with AsyncClient(self._token) as client:
                bonds = await self._get_tradable_bonds(client)
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
