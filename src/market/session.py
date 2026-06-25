import asyncio
import logging

from t_tech.invest.grpc import AsyncClient  # type: ignore
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.config import settings
from src.market.api import fetch_account_id, fetch_active_bid_orders
from src.market.bid_order_registry import ActiveBidOrder, BidOrderRegistry
from src.market.bond_catalog import BondCatalog
from src.market.context import MarketContext
from src.market.cooldown_registry import CooldownRegistry
from src.market.domain import MaturityEventType
from src.market.providers import BondProvider, MaturityProvider, OrderStateProvider
from src.market.use_cases import (
    process_ask_sniper,
    process_bid_order_state,
    process_bid_waiter,
    process_maturity,
    refresh_all_bids,
)
from src.market.utils import to_float
from src.stats import MaturityRepository, PurchaseRepository

logger = logging.getLogger(__name__)


async def _with_retry(fn, *args, **kwargs) -> None:
    while True:
        try:
            await fn(*args, **kwargs)
        except Exception:
            logger.exception(f"Unexpected error in {fn.__name__}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)


async def _sync_bid_registry_from_broker(
    client: AsyncServices, account_id: str, bid_registry: BidOrderRegistry
) -> None:
    existing = await fetch_active_bid_orders(client, account_id)
    for order in existing:
        bid_registry.add(
            ActiveBidOrder(
                order_id=order.order_id,
                figi=order.figi,
                price_percent=to_float(order.initial_security_price),
                quantity=order.lots_requested - order.lots_executed,
            )
        )
    logger.info(f"Synced {len(existing)} active bid orders from broker")


async def start_market_session() -> None:
    purchase_repo = PurchaseRepository()
    maturity_repo = MaturityRepository()
    bid_registry = BidOrderRegistry()
    catalog = BondCatalog()
    cooldown_registry = CooldownRegistry()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)

        await _sync_bid_registry_from_broker(client, account_id, bid_registry)

        ctx = MarketContext(
            client=client,
            account_id=account_id,
            bid_registry=bid_registry,
            catalog=catalog,
            cooldown_registry=cooldown_registry,
            purchase_repo=purchase_repo,
            maturity_repo=maturity_repo,
        )

        bond_provider = BondProvider(catalog)
        maturity_provider = MaturityProvider(account_id)
        order_state_provider = OrderStateProvider(account_id)

        async def bond_loop():
            async for bond in bond_provider.stream():
                if not bond.orderbook.asks and not bond.orderbook.bids:
                    logger.debug(f"Skipped {bond.ticker}: empty orderbook")
                    continue
                try:
                    await process_ask_sniper(ctx, bond)
                    await process_bid_waiter(ctx, bond)
                except Exception:
                    logger.exception(f"Failed to process tick for {bond.ticker}")

        async def maturity_loop():
            async for event in maturity_provider.stream():
                try:
                    await process_maturity(ctx, event)
                    if event.event_type == MaturityEventType.REPAYMENT:
                        await refresh_all_bids(ctx)
                except Exception:
                    logger.exception(
                        f"Failed to process maturity event for {event.bond_figi}"
                    )

        async def order_state_loop():
            async for event in order_state_provider.stream():
                try:
                    await process_bid_order_state(ctx, event)
                except Exception:
                    logger.exception(
                        f"Failed to process order state for {event.order_id}"
                    )

        await asyncio.gather(
            _with_retry(bond_loop),
            _with_retry(maturity_loop),
            _with_retry(order_state_loop),
        )
