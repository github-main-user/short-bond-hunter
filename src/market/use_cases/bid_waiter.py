import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from t_tech.invest import OrderExecutionReportStatus, PortfolioPosition
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.schemas import OrderStateStreamOrderState

from src.config import Settings, settings
from src.market.api import (
    cancel_bid_order,
    fetch_account_balance_rub,
    fetch_existing_bonds,
    fetch_tmon_etf_price_at,
    place_bid_order,
    replace_bid_order,
)
from src.market.domain import EnrichedBond
from src.market.messages import compose_bid_fill_notification
from src.market.order_registry import ActiveBidOrder, OrderRegistry
from src.market.utils import normalize_quotation
from src.stats import PurchaseRepository
from src.stats.models import PurchaseStrategy
from src.telegram import notify

logger = logging.getLogger(__name__)


def _decide_target_price(
    bond: EnrichedBond, our_order: ActiveBidOrder | None
) -> float | None:
    top = bond.bid_price_percent
    if top <= 0:
        return None
    if our_order and our_order.price >= top:
        return our_order.price
    return top + bond.min_price_increment


def _compute_bid_quantity(
    bond: EnrichedBond,
    target_real_price: float,
    balance: float,
    existing_position: PortfolioPosition | None,
    registry: OrderRegistry,
    settings: Settings,
) -> int:
    qty_by_bid_cap = int(settings.BID_MAX_SUM_PER_BOND // target_real_price)

    sniper_held_value = (
        normalize_quotation(existing_position.quantity)
        * normalize_quotation(existing_position.current_price)
        if existing_position
        else 0.0
    )
    qty_by_shared_cap = int(
        max(0.0, settings.MAX_SUM_PER_BOND - sniper_held_value) // target_real_price
    )

    effective_balance = balance + registry.reserved_value_for(bond.figi)
    qty_by_balance = int(effective_balance // target_real_price)

    return min(qty_by_bid_cap, qty_by_shared_cap, qty_by_balance)


async def _place(
    client: AsyncServices,
    account_id: str,
    bond: EnrichedBond,
    registry: OrderRegistry,
    purchase_repo: PurchaseRepository,
    qty: int,
    price_percent: float,
) -> None:
    response = await place_bid_order(client, account_id, bond.figi, qty, price_percent)
    if response is None:
        return
    if response.lots_executed > 0:
        await _record_fill(
            client,
            account_id,
            bond,
            purchase_repo,
            response.lots_executed,
            price_percent,
        )
    registry.add(
        ActiveBidOrder(
            order_id=response.order_id,
            figi=bond.figi,
            price=price_percent,
            quantity=response.lots_requested - response.lots_executed,
        )
    )
    logger.info(f"Placed bid for {bond.ticker}: {qty} lots at {price_percent:.4f}%")


async def _replace(
    client: AsyncServices,
    account_id: str,
    bond: EnrichedBond,
    registry: OrderRegistry,
    purchase_repo: PurchaseRepository,
    old: ActiveBidOrder,
    qty: int,
    price_percent: float,
) -> None:
    response = await replace_bid_order(
        client, account_id, old.order_id, qty, price_percent
    )
    if response is None:
        return
    if response.lots_executed > 0:
        await _record_fill(
            client,
            account_id,
            bond,
            purchase_repo,
            response.lots_executed,
            price_percent,
        )
    registry.remove(bond.figi, old.order_id)
    registry.add(
        ActiveBidOrder(
            order_id=response.order_id,
            figi=bond.figi,
            price=price_percent,
            quantity=response.lots_requested - response.lots_executed,
        )
    )
    logger.info(
        f"Replaced bid for {bond.ticker}: {old.order_id} -> {response.order_id}, "
        f"qty={qty}, price={price_percent:.4f}%"
    )


async def _cancel(
    client: AsyncServices,
    account_id: str,
    bond: EnrichedBond,
    registry: OrderRegistry,
    order: ActiveBidOrder,
) -> None:
    await cancel_bid_order(client, account_id, order.order_id)
    registry.remove(bond.figi, order.order_id)
    logger.info(f"Cancelled bid for {bond.ticker}: {order.order_id}")


async def process_bid_for_orderbook(
    client: AsyncServices,
    bond: EnrichedBond,
    registry: OrderRegistry,
    purchase_repo: PurchaseRepository,
    account_id: str,
) -> None:
    if bond.ticker in settings.BLACK_LIST_TICKERS:
        return

    existing_bids = registry.bids_for(bond.figi)
    if len(existing_bids) > 1:
        logger.warning(f"Multiple bid orders for {bond.ticker}, expected at most 1")
    our_order = existing_bids[0] if existing_bids else None

    target_price = _decide_target_price(bond, our_order)
    if target_price is None:
        return

    yield_at_target = bond.annual_yield_at(target_price)

    if not (
        settings.BID_ANNUAL_YIELD_MIN
        <= yield_at_target
        <= settings.BID_ANNUAL_YIELD_MAX
    ):
        if our_order:
            logger.info(
                f"Yield {yield_at_target:.2f}% for {bond.ticker} is outside the bid range "
                f"({settings.BID_ANNUAL_YIELD_MIN}%, {settings.BID_ANNUAL_YIELD_MAX}%); cancelling"
            )
            await _cancel(client, account_id, bond, registry, our_order)
        return

    balance = await fetch_account_balance_rub(client, account_id)
    if balance is None:
        return

    existing_positions = await fetch_existing_bonds(client, account_id)
    existing_position = existing_positions.get(bond.ticker)

    target_real_price = bond.real_price_at(target_price)
    if target_real_price <= 0:
        return

    target_qty = _compute_bid_quantity(
        bond, target_real_price, balance, existing_position, registry, settings
    )

    if target_qty == 0:
        if our_order:
            logger.info(f"Target qty for {bond.ticker} is 0; cancelling existing bid")
            await _cancel(client, account_id, bond, registry, our_order)
        return

    if our_order is None:
        await _place(
            client,
            account_id,
            bond,
            registry,
            purchase_repo,
            target_qty,
            target_price,
        )
        return

    if our_order.price == target_price and our_order.quantity == target_qty:
        return

    await _replace(
        client,
        account_id,
        bond,
        registry,
        purchase_repo,
        our_order,
        target_qty,
        target_price,
    )


async def _record_fill(
    client: AsyncServices,
    account_id: str,
    bond: EnrichedBond,
    purchase_repo: PurchaseRepository,
    lots_filled: int,
    price_percent: float,
) -> None:
    tmon_price = await fetch_tmon_etf_price_at(
        client, datetime.now(tz=timezone.utc)
    )
    purchase_repo.create(
        bond_name=bond.name,
        bond_figi=bond.figi,
        bond_ticker=bond.ticker,
        quantity=lots_filled,
        nominal=bond.nominal,
        price=bond.current_price_at(price_percent),
        aci_value=bond.aci_value,
        commission_percent=bond.commission_percent,
        real_price=bond.real_price_at(price_percent),
        coupons_sum=bond.coupons_sum,
        risk_level=bond.risk_level,
        tmon_price=tmon_price,
        expected_maturity_date=bond.maturity_date,
        strategy=PurchaseStrategy.BID_WAITER,
    )
    remaining = await fetch_account_balance_rub(client, account_id)
    await notify(
        compose_bid_fill_notification(bond, lots_filled, price_percent, remaining)
    )


async def process_order_state(
    client: AsyncServices,
    event: OrderStateStreamOrderState,
    registry: OrderRegistry,
    purchase_repo: PurchaseRepository,
    figi_to_bond: dict[str, EnrichedBond],
    account_id: str,
) -> None:
    if not registry.has_order_id(event.order_id):
        return

    existing = registry.find_by_order_id(event.order_id)
    if existing is None:
        return

    delta_lots = existing.quantity - event.lots_left
    if delta_lots > 0:
        bond = figi_to_bond.get(existing.figi)
        if bond is None:
            logger.warning(
                f"Filled order {event.order_id} for unknown figi {existing.figi}; "
                f"skipping purchase record"
            )
        else:
            await _record_fill(
                client,
                account_id,
                bond,
                purchase_repo,
                delta_lots,
                existing.price,
            )

    status = event.execution_report_status
    if status in (
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED,
    ):
        registry.remove(existing.figi, event.order_id)
    elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
        registry.set_quantity(existing.figi, event.order_id, event.lots_left)


async def refresh_all_bids(
    client: AsyncServices,
    bonds: Iterable[EnrichedBond],
    registry: OrderRegistry,
    purchase_repo: PurchaseRepository,
    account_id: str,
) -> None:
    for bond in list(bonds):
        await process_bid_for_orderbook(
            client, bond, registry, purchase_repo, account_id
        )
