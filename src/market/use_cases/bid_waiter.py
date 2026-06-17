import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from t_tech.invest import OrderExecutionReportStatus
from t_tech.invest.schemas import OrderStateStreamOrderState

from src.config import settings
from src.market.api import (
    cancel_bid_order,
    fetch_account_balance_rub,
    fetch_tmon_etf_price_at,
    place_bid_order,
    replace_bid_order,
)
from src.market.bid_order_registry import ActiveBidOrder
from src.market.context import MarketContext
from src.market.domain import EnrichedBond
from src.market.messages import compose_bid_fill_notification
from src.stats.models import PurchaseStrategy
from src.telegram import notify

logger = logging.getLogger(__name__)


def _decide_target_price_percent(
    bond: EnrichedBond, our_order: ActiveBidOrder | None
) -> float | None:
    bid = bond.bid_price_percent
    ask = bond.ask_price_percent

    if bid <= 0:
        logger.debug(f"Skipped bid for {bond.ticker}: no bids in orderbook")
        return None
    if our_order and our_order.price_percent >= bid:
        return our_order.price_percent

    target = bid + bond.min_price_increment

    if ask > 0 and target >= ask:
        if bid < ask:
            return bid
        logger.debug(f"Skipped bid for {bond.ticker}: book is locked/crossed")
        return None
    return target


def _compute_bid_quantity(
    bond: EnrichedBond,
    target_real_price: float,
    balance: float,
    ctx: MarketContext,
) -> int:
    qty_by_bid_cap = int(settings.BID_MAX_SUM_PER_BOND // target_real_price)

    reserved_rub = sum(
        bond.at(o.price_percent).real_price * o.quantity
        for o in ctx.bid_registry.bids_for(bond.figi)
    )
    effective_balance = balance + reserved_rub
    qty_by_balance = int(effective_balance // target_real_price)

    qty = min(qty_by_bid_cap, qty_by_balance)
    if qty == 0:
        logger.debug(
            f"Skipped bid for {bond.ticker}: quantity is 0 "
            f"(by_bid_cap={qty_by_bid_cap}, by_balance={qty_by_balance})"
        )
    return qty


async def _place_or_replace_bid(
    ctx: MarketContext,
    bond: EnrichedBond,
    qty: int,
    price_percent: float,
    old: ActiveBidOrder | None = None,
) -> None:
    if old is None:
        response = await place_bid_order(
            ctx.client, ctx.account_id, bond, qty, price_percent
        )
    else:
        response = await replace_bid_order(
            ctx.client, ctx.account_id, bond, old.order_id, qty, price_percent
        )
    if response is None:
        return

    if old is not None:
        ctx.bid_registry.remove(bond.figi, old.order_id)
    lots_left = response.lots_requested - response.lots_executed
    if lots_left > 0:
        ctx.bid_registry.add(
            ActiveBidOrder(
                order_id=response.order_id,
                figi=bond.figi,
                price_percent=price_percent,
                quantity=lots_left,
            )
        )

    view = bond.at(price_percent)
    if old is None:
        head = f"Placed bid for {bond.ticker}: {qty} lots at {view.current_price:.2f}₽"
    else:
        head = (
            f"Replaced bid for {bond.ticker}: {old.order_id} -> {response.order_id}, "
            f"qty={qty}, price {view.current_price:.2f}₽"
        )
    logger.info(
        f"{head} (yield {view.annual_yield:.2f}%, cost {view.real_price:.2f}₽, "
        f"top bid {bond.bid.current_price:.2f}₽)"
    )

    if response.lots_executed > 0:
        await _record_fill(ctx, bond, response.lots_executed, price_percent)


async def _cancel_bid(
    ctx: MarketContext, bond: EnrichedBond, order: ActiveBidOrder
) -> None:
    await cancel_bid_order(ctx.client, ctx.account_id, order.order_id)
    ctx.bid_registry.remove(bond.figi, order.order_id)
    logger.info(f"Cancelled bid for {bond.ticker}: {order.order_id}")


async def process_bid_waiter(ctx: MarketContext, bond: EnrichedBond) -> None:
    if bond.ticker in settings.BLACK_LIST_TICKERS:
        return

    existing_bids = ctx.bid_registry.bids_for(bond.figi)
    if len(existing_bids) > 1:
        logger.warning(f"Multiple bid orders for {bond.ticker}, expected at most 1")
    our_order = existing_bids[0] if existing_bids else None

    target_price = _decide_target_price_percent(bond, our_order)
    if target_price is None:
        return

    target = bond.at(target_price)

    if not (
        settings.BID_MIN_ANNUAL_YIELD
        <= target.annual_yield
        <= settings.BID_MAX_ANNUAL_YIELD
    ):
        if our_order:
            logger.info(
                f"Yield {target.annual_yield:.2f}% for {bond.ticker} is outside the bid range "
                f"[{settings.BID_MIN_ANNUAL_YIELD}%, {settings.BID_MAX_ANNUAL_YIELD}%]; cancelling"
            )
            await _cancel_bid(ctx, bond, our_order)
        else:
            logger.debug(
                f"Skipped bid for {bond.ticker}: target yield {target.annual_yield:.2f}% "
                f"is outside the bid range "
                f"[{settings.BID_MIN_ANNUAL_YIELD}%, {settings.BID_MAX_ANNUAL_YIELD}%]"
            )
        return

    balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    if balance is None:
        return

    if target.real_price <= 0:
        return

    target_qty = _compute_bid_quantity(bond, target.real_price, balance, ctx)

    if target_qty == 0:
        if our_order:
            logger.info(f"Target qty for {bond.ticker} is 0; cancelling existing bid")
            await _cancel_bid(ctx, bond, our_order)
        return

    if our_order is None:
        await _place_or_replace_bid(ctx, bond, target_qty, target_price)
        return

    if our_order.price_percent == target_price and our_order.quantity == target_qty:
        logger.debug(
            f"Bid for {bond.ticker} already at target: "
            f"{target.current_price:.2f}₽, qty={target_qty}"
        )
        return

    await _place_or_replace_bid(ctx, bond, target_qty, target_price, old=our_order)


async def _record_fill(
    ctx: MarketContext,
    bond: EnrichedBond,
    lots_filled: int,
    price_percent: float,
) -> None:
    view = bond.at(price_percent)
    logger.info(
        f"Bid filled for {bond.ticker}: {lots_filled} lots at {view.current_price:.2f}₽ "
        f"(yield {view.annual_yield:.2f}%)"
    )
    tmon_price = await fetch_tmon_etf_price_at(
        ctx.client, datetime.now(tz=timezone.utc)
    )
    ctx.purchase_repo.create(
        bond_name=bond.name,
        bond_figi=bond.figi,
        bond_ticker=bond.ticker,
        quantity=lots_filled,
        nominal=bond.nominal,
        price=view.current_price,
        aci_value=bond.aci_value,
        commission_percent=bond.commission_percent,
        real_price=view.real_price,
        coupons_sum=bond.coupons_sum,
        risk_level=bond.risk_level,
        tmon_price=tmon_price,
        expected_maturity_date=bond.maturity_date,
        strategy=PurchaseStrategy.BID_WAITER,
    )
    remaining = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    await notify(compose_bid_fill_notification(bond, view, lots_filled, remaining))


async def process_bid_order_state(
    ctx: MarketContext,
    event: OrderStateStreamOrderState,
    figi_to_bond: dict[str, EnrichedBond],
) -> None:
    existing = ctx.bid_registry.find_by_order_id(event.order_id)
    if existing is None:
        return

    bond = figi_to_bond.get(existing.figi)
    name = bond.ticker if bond else existing.figi

    delta_lots = existing.quantity - event.lots_left - event.lots_cancelled
    if delta_lots > 0:
        if bond is None:
            logger.warning(
                f"Filled order {event.order_id} for unknown figi {existing.figi}; "
                f"skipping purchase record"
            )
        else:
            await _record_fill(ctx, bond, delta_lots, existing.price_percent)

    status = event.execution_report_status
    if status in (
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED,
    ):
        ctx.bid_registry.remove(existing.figi, event.order_id)
        status_name = status.name.removeprefix("EXECUTION_REPORT_STATUS_")
        logger.info(
            f"Bid for {name} removed from registry: {event.order_id} ({status_name})"
        )
    elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
        ctx.bid_registry.set_quantity(existing.figi, event.order_id, event.lots_left)
        logger.info(f"Bid for {name} partially filled: {event.lots_left} lots left")


async def refresh_all_bids(ctx: MarketContext, bonds: Iterable[EnrichedBond]) -> None:
    for bond in list(bonds):
        await process_bid_waiter(ctx, bond)
