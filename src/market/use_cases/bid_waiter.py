from datetime import datetime, timezone

import structlog
from t_tech.invest.grpc.schemas import (
    OrderExecutionReportStatus,
    OrderStateStreamResponse,
    PortfolioPosition,
)

from src.config import settings
from src.market.api import (
    cancel_bid_order,
    fetch_account_balance_rub,
    fetch_bond_positions,
    fetch_tmon_etf_price_at,
    place_bid_order,
    replace_bid_order,
)
from src.market.bid_order_registry import ActiveBidOrder
from src.market.context import MarketContext
from src.market.domain import EnrichedBond
from src.market.messages import compose_bid_fill_notification
from src.market.utils import to_float
from src.stats.models import PurchaseStrategy
from src.telegram import notify

log = structlog.get_logger(__name__)


def _decide_target_price_percent(
    bond: EnrichedBond, our_order: ActiveBidOrder | None
) -> float | None:
    bid = bond.bid_price_percent
    ask = bond.ask_price_percent

    if bid <= 0:
        log.debug(
            "bid_book_skipped",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="no_bids",
        )
        return None
    if our_order and our_order.price_percent >= bid:
        return our_order.price_percent

    target = bid + bond.min_price_increment

    if ask > 0 and target >= ask:
        if bid < ask:
            return bid
        log.debug(
            "bid_book_skipped",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="locked_or_crossed_book",
            target_price=target,
            ask_price=bond.ask.current_price,
            bid_price=bond.bid.current_price,
        )
        return None
    return target


def _compute_bid_quantity(
    bond: EnrichedBond,
    target_real_price: float,
    balance: float,
    existing_position: PortfolioPosition | None,
    ctx: MarketContext,
) -> int:
    qty_by_bid_cap = int(settings.BID_MAX_SUM_PER_BOND // target_real_price)

    sniper_held_value = (
        to_float(existing_position.quantity) * to_float(existing_position.current_price)
        if existing_position
        else 0.0
    )
    qty_by_shared_cap = int(
        max(0.0, settings.TOTAL_MAX_SUM_PER_BOND - sniper_held_value)
        // target_real_price
    )

    reserved_rub = sum(
        bond.at(o.price_percent).real_price * o.quantity
        for o in ctx.bid_registry.bids_for(bond.figi)
    )
    effective_balance = balance + reserved_rub
    qty_by_balance = int(effective_balance // target_real_price)

    qty = min(qty_by_bid_cap, qty_by_shared_cap, qty_by_balance)
    if qty == 0:
        log.debug(
            "bid_quantity_skipped",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="zero_quantity",
            qty_by_bid_cap=qty_by_bid_cap,
            qty_by_shared_cap=qty_by_shared_cap,
            qty_by_balance=qty_by_balance,
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
        log.info(
            "bid_placed",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            order_id=response.order_id,
            quantity=qty,
            current_price=view.current_price,
            real_price=view.real_price,
            annual_yield=view.annual_yield,
            top_bid_price=bond.bid.current_price,
        )
    else:
        log.info(
            "bid_replaced",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            old_order_id=old.order_id,
            new_order_id=response.order_id,
            quantity=qty,
            current_price=view.current_price,
            real_price=view.real_price,
            annual_yield=view.annual_yield,
            top_bid_price=bond.bid.current_price,
        )

    if response.lots_executed > 0:
        await _record_fill(ctx, bond, response.lots_executed, price_percent)


async def _cancel_bid(
    ctx: MarketContext, bond: EnrichedBond, order: ActiveBidOrder
) -> None:
    await cancel_bid_order(ctx.client, ctx.account_id, order.order_id)
    ctx.bid_registry.remove(bond.figi, order.order_id)
    log.info(
        "bid_cancelled",
        name=bond.name,
        figi=bond.figi,
        ticker=bond.ticker,
        order_id=order.order_id,
    )


async def process_bid_waiter(ctx: MarketContext, bond: EnrichedBond) -> None:
    if bond.ticker in settings.BLACK_LISTED_TICKERS:
        return

    existing_bids = ctx.bid_registry.bids_for(bond.figi)
    if len(existing_bids) > 1:
        log.warning(
            "multiple_bids_detected",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            count=len(existing_bids),
        )
    our_order = existing_bids[0] if existing_bids else None

    target_price = _decide_target_price_percent(bond, our_order)
    if target_price is None:
        return

    target_view = bond.at(target_price)

    if not (
        settings.BID_MIN_ANNUAL_YIELD
        <= target_view.annual_yield
        <= settings.BID_MAX_ANNUAL_YIELD
    ):
        if our_order:
            log.info(
                "bid_yield_out_of_range",
                name=bond.name,
                figi=bond.figi,
                ticker=bond.ticker,
                target_yield=target_view.annual_yield,
                bid_min_annual_yield=settings.BID_MIN_ANNUAL_YIELD,
                bid_max_annual_yield=settings.BID_MAX_ANNUAL_YIELD,
                action="cancel",
            )
            await _cancel_bid(ctx, bond, our_order)
        else:
            log.debug(
                "bid_yield_out_of_range",
                name=bond.name,
                figi=bond.figi,
                ticker=bond.ticker,
                target_yield=target_view.annual_yield,
                bid_min_annual_yield=settings.BID_MIN_ANNUAL_YIELD,
                bid_max_annual_yield=settings.BID_MAX_ANNUAL_YIELD,
                action="skip",
            )
        return

    balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    if balance is None:
        return

    existing_positions = await fetch_bond_positions(ctx.client, ctx.account_id)
    existing_position = existing_positions.get(bond.figi)

    if target_view.real_price <= 0:
        return

    target_qty = _compute_bid_quantity(
        bond, target_view.real_price, balance, existing_position, ctx
    )

    if target_qty == 0:
        if our_order:
            log.info(
                "bid_quantity_skipped",
                name=bond.name,
                figi=bond.figi,
                ticker=bond.ticker,
                reason="zero_quantity",
                action="cancel_existing",
            )
            await _cancel_bid(ctx, bond, our_order)
        return

    if our_order is None:
        if ctx.cooldown_registry.on_cooldown(
            PurchaseStrategy.BID_WAITER, bond.figi, settings.BID_COOLDOWN_SECONDS
        ):
            log.debug(
                "bid_cooldown_active",
                name=bond.name,
                figi=bond.figi,
                ticker=bond.ticker,
            )
            return
        await _place_or_replace_bid(ctx, bond, target_qty, target_price)
        return

    if our_order.price_percent == target_price and our_order.quantity == target_qty:
        log.debug(
            "bid_already_at_target",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            current_price=target_view.current_price,
            quantity=target_qty,
        )
        return

    await _place_or_replace_bid(ctx, bond, target_qty, target_price, old=our_order)


async def _record_fill(
    ctx: MarketContext, bond: EnrichedBond, lots_filled: int, price_percent: float
) -> None:
    view = bond.at(price_percent)
    total_price = view.real_price * lots_filled
    log.info(
        "bid_filled",
        name=bond.name,
        figi=bond.figi,
        ticker=bond.ticker,
        lots_filled=lots_filled,
        total_price=total_price,
        annual_yield=view.annual_yield,
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
    ctx.cooldown_registry.mark(PurchaseStrategy.BID_WAITER, bond.figi)
    remaining = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    await notify(compose_bid_fill_notification(bond, view, lots_filled, remaining))


async def process_bid_order_state(
    ctx: MarketContext,
    event: OrderStateStreamResponse.OrderState,
) -> None:
    existing_order = ctx.bid_registry.find_by_order_id(event.order_id)
    if existing_order is None:
        return

    bond = ctx.catalog.get(existing_order.figi)

    newly_filled = existing_order.quantity - event.lots_left - event.lots_cancelled
    if newly_filled > 0:
        if bond is None:
            log.warning(
                "bid_order_unknown_bond_warning",
                order_id=event.order_id,
                figi=existing_order.figi,
                lots_filled=newly_filled,
            )
        else:
            await _record_fill(ctx, bond, newly_filled, existing_order.price_percent)

    status = event.execution_report_status
    if status in (
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_CANCELLED,
        OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED,
    ):
        ctx.bid_registry.remove(existing_order.figi, event.order_id)
        status_name = status.name.removeprefix("EXECUTION_REPORT_STATUS_")
        log.info(
            "bid_order_removed",
            figi=existing_order.figi,
            order_id=event.order_id,
            status=status_name,
            lots_left=event.lots_left,
            lots_cancelled=event.lots_cancelled,
        )
    elif status == OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL:
        ctx.bid_registry.set_quantity(
            existing_order.figi, event.order_id, event.lots_left
        )
        log.info(
            "bid_order_partially_filled",
            figi=existing_order.figi,
            order_id=event.order_id,
            lots_left=event.lots_left,
        )


async def refresh_all_bids(ctx: MarketContext) -> None:
    for bond in ctx.catalog.all():
        await process_bid_waiter(ctx, bond)
