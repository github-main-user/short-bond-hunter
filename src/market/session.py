import asyncio
import logging

from t_tech.invest import AsyncClient

from src.config import settings
from src.market.api import fetch_account_id, fetch_active_bid_orders
from src.market.context import MarketContext
from src.market.domain import MaturityEventType
from src.market.order_registry import ActiveBidOrder, OrderRegistry
from src.market.providers import BondProvider, MaturityProvider, OrderStateProvider
from src.market.use_cases import (
    process_bid_for_orderbook,
    process_bond,
    process_maturity,
    process_order_state,
    refresh_all_bids,
)
from src.market.utils import normalize_quotation
from src.stats import MaturityRepository, PurchaseRepository

logger = logging.getLogger(__name__)


async def _with_retry(fn, *args, **kwargs) -> None:
    while True:
        try:
            await fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unexpected error in {fn.__name__}: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)


async def _sync_registry_from_broker(
    client, account_id: str, registry: OrderRegistry
) -> None:
    existing = await fetch_active_bid_orders(client, account_id)
    for order in existing:
        registry.add(
            ActiveBidOrder(
                order_id=order.order_id,
                figi=order.figi,
                price=normalize_quotation(order.initial_security_price),
                quantity=order.lots_requested - order.lots_executed,
            )
        )
    logger.info(f"Synced {len(existing)} active bid orders from broker")


async def start_market_session() -> None:
    purchase_repo = PurchaseRepository()
    maturity_repo = MaturityRepository()
    registry = OrderRegistry()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)

        await _sync_registry_from_broker(client, account_id, registry)

        ctx = MarketContext(
            client=client,
            account_id=account_id,
            registry=registry,
            purchase_repo=purchase_repo,
        )

        bond_provider = BondProvider(settings)
        maturity_provider = MaturityProvider(account_id, settings)
        order_state_provider = OrderStateProvider(account_id, settings)

        async def bond_loop():
            async for bond in bond_provider.stream():
                await process_bond(ctx, bond)
                await process_bid_for_orderbook(ctx, bond)

        async def maturity_loop():
            async for event in maturity_provider.stream():
                await process_maturity(client, maturity_repo, event)
                if event.event_type == MaturityEventType.REPAYMENT:
                    await refresh_all_bids(ctx, bond_provider.figi_to_bond.values())

        async def order_state_loop():
            async for event in order_state_provider.stream():
                await process_order_state(ctx, event, bond_provider.figi_to_bond)

        await asyncio.gather(
            _with_retry(bond_loop),
            _with_retry(maturity_loop),
            _with_retry(order_state_loop),
        )
