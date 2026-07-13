import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import structlog
from t_tech.invest.grpc import AsyncClient  # type: ignore
from t_tech.invest.grpc.schemas import (
    Bond,
    MarketDataRequest,
    OrderBookInstrument,
    RiskLevel,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.config import settings
from src.market.api import (
    fetch_coupons_sum,
    fetch_orderbook,
    fetch_raw_bonds,
    fetch_user_commission,
)
from src.market.bond_catalog import BondCatalog
from src.market.domain import EnrichedBond

log = structlog.get_logger(__name__)


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
    def __init__(self, catalog: BondCatalog) -> None:
        self._catalog = catalog

    async def _fetch_tradable_bonds(self, client: AsyncServices) -> list[EnrichedBond]:
        user_commission = await fetch_user_commission(client)
        raw_bonds = await fetch_raw_bonds(client)
        log.info("bonds_fetched", count=len(raw_bonds))

        filtered = _filter_bonds(raw_bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
        log.info(
            "bonds_filtered",
            count=len(filtered),
            max_days_to_maturity=settings.DAYS_TO_MATURITY_MAX,
        )

        coupon_sums = await asyncio.gather(
            *[
                fetch_coupons_sum(client, bond.figi, bond.maturity_date)
                for bond in filtered
            ]
        )
        orderbooks = await asyncio.gather(
            *[fetch_orderbook(client, bond.figi) for bond in filtered]
        )

        bonds = [
            EnrichedBond.from_bond(
                bond,
                commission_percent=user_commission,
                coupons_sum=coupon_sum,
                orderbook=orderbook,
            )
            for bond, coupon_sum, orderbook in zip(filtered, coupon_sums, orderbooks)
        ]
        return bonds

    async def stream(self) -> AsyncGenerator[EnrichedBond]:
        while True:
            async with AsyncClient(settings.TINVEST_TOKEN) as client:
                bonds = await self._fetch_tradable_bonds(client)

                self._catalog.replace_all(bonds)
                log.info("bond_catalog_replaced", count=len(bonds))

                for bond in bonds:
                    yield bond
                async for bond in self._stream_price_updates(client, bonds):
                    yield bond

    async def _stream_price_updates(
        self, client: AsyncServices, bonds: list[EnrichedBond]
    ) -> AsyncGenerator[EnrichedBond]:
        async def request_iterator():
            yield MarketDataRequest(
                subscribe_order_book_request=SubscribeOrderBookRequest(
                    subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                    instruments=[
                        OrderBookInstrument(figi=b.figi, depth=1) for b in bonds
                    ],
                )
            )
            await asyncio.Event().wait()

        log.info("orderbook_subscribed", count=len(bonds))

        try:
            async with asyncio.timeout(settings.BOND_REFRESH_INTERVAL_SECONDS):
                async for marketdata in client.market_data_stream.market_data_stream(
                    request_iterator()
                ):
                    if not marketdata.orderbook:
                        log.debug("market_data_skipped", reason="no_orderbook")
                        continue

                    bond = self._catalog.get(marketdata.orderbook.figi)
                    if not bond:
                        log.debug(
                            "price_update_skipped",
                            figi=marketdata.orderbook.figi,
                            reason="not_in_catalog",
                        )
                        continue

                    before = (bond.ask.real_price, bond.bid.real_price)
                    bond.update(marketdata.orderbook)

                    if (bond.ask.real_price, bond.bid.real_price) != before:
                        yield bond
        except TimeoutError:
            log.info("bond_refresh_interval_reached")
