import asyncio
import logging

from datetime import datetime, timezone

from t_tech.invest import (
    AsyncClient,
    Bond,
    MarketDataRequest,
    OrderBook,
    OrderBookInstrument,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.schemas import RiskLevel

from src.config import settings
from src.market.api import fetch_coupons_sum, fetch_raw_bonds, fetch_user_commission
from src.market.domain import EnrichedBond

logger = logging.getLogger(__name__)


def _filter_bonds(bonds: list[Bond], maximum_days: int) -> list[Bond]:
    now = datetime.now(tz=timezone.utc).date()
    return [
        bond
        for bond in bonds
        if (
            not bond.for_qual_investor_flag
            and not bond.perpetual_flag
            and bond.currency == "rub"
            and bond.nominal.currency == "rub"
            and (bond.maturity_date.date() - now).days <= maximum_days
            and (
                RiskLevel.RISK_LEVEL_UNSPECIFIED
                < bond.risk_level
                < RiskLevel.RISK_LEVEL_HIGH
            )
        )
    ]


class BondProvider:
    def __init__(self) -> None:
        self.figi_to_bond: dict[str, EnrichedBond] = {}

    async def _get_tradable_bonds(self, client: AsyncServices) -> list[EnrichedBond]:
        user_commission = await fetch_user_commission(client)
        raw_bonds = await fetch_raw_bonds(client)
        logger.info(f"Got {len(raw_bonds)} bonds")

        filtered = _filter_bonds(raw_bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
        logger.info(f"{len(filtered)} bonds left after filtering")

        coupon_sums = await asyncio.gather(
            *[
                fetch_coupons_sum(client, bond.figi, bond.maturity_date)
                for bond in filtered
            ]
        )

        bonds = [
            EnrichedBond.from_bond(
                bond,
                commission_percent=user_commission,
                coupons_sum=coupon_sum,
                orderbook=OrderBook(figi=bond.figi, asks=[], bids=[]),
            )
            for bond, coupon_sum in zip(filtered, coupon_sums)
        ]
        self.figi_to_bond = {b.figi: b for b in bonds}
        return bonds

    async def stream(self):
        while True:
            async with AsyncClient(settings.TINVEST_TOKEN) as client:
                bonds = await self._get_tradable_bonds(client)
                async for bond in self._stream_price_updates(client, bonds):
                    yield bond

    async def _stream_price_updates(
        self, client: AsyncServices, bonds: list[EnrichedBond]
    ):
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
            async with asyncio.timeout(settings.BOND_REFRESH_INTERVAL_SECONDS):
                async for marketdata in client.market_data_stream.market_data_stream(
                    request_iterator()
                ):
                    if not marketdata.orderbook:
                        logger.info("Skipped market data: no orderbook")
                        continue

                    bond = self.figi_to_bond.get(marketdata.orderbook.figi)
                    if not bond:
                        logger.debug(
                            f"Skipped update for bond {marketdata.orderbook.figi} (figi):"
                            " not in the list"
                        )
                        continue

                    old_ask = bond.ask.real_price
                    old_bid = bond.bid.real_price
                    bond.update(marketdata.orderbook)

                    if old_ask != bond.ask.real_price or old_bid != bond.bid.real_price:
                        yield bond
        except TimeoutError:
            logger.info("Bonds update interval reached. Re-fetching...")
