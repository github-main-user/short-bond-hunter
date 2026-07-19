from datetime import datetime, timezone

import structlog

from t_tech.invest.grpc.schemas import PortfolioPosition

from src.config import settings
from src.market.api import (
    buy_at_ask,
    fetch_account_balance_rub,
    fetch_bond_positions,
    fetch_tmon_etf_price_at,
)
from src.market.bid_order_registry import BidOrderRegistry
from src.market.context import MarketContext
from src.market.domain import EnrichedBond
from src.market.messages import compose_ask_snipe_notification
from src.market.utils import to_float
from src.stats.models import PurchaseStrategy
from src.telegram import notify

log = structlog.get_logger(__name__)


def _is_eligible_for_snipe(bond: EnrichedBond) -> bool:
    if bond.ticker in settings.BLACK_LISTED_TICKERS:
        log.debug(
            "ask_ineligible",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="blacklisted",
        )
        return False

    if not (
        settings.ASK_MIN_ANNUAL_YIELD
        <= bond.ask.annual_yield
        <= settings.ASK_MAX_ANNUAL_YIELD
    ):
        log.debug(
            "ask_ineligible",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="yield_out_of_range",
            annual_yield=bond.ask.annual_yield,
            ask_min_annual_yield=settings.ASK_MIN_ANNUAL_YIELD,
            ask_max_annual_yield=settings.ASK_MAX_ANNUAL_YIELD,
        )
        return False

    if bond.ask.real_price <= 0:
        log.debug(
            "ask_ineligible",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="non_positive_ask_price",
            ask_real_price=bond.ask.real_price,
        )
        return False

    return True


def _compute_purchase_quantity(
    bond: EnrichedBond,
    balance: float,
    existing_position: PortfolioPosition | None,
    bid_registry: BidOrderRegistry,
) -> int:
    qty_by_purchase_cap = int(settings.ASK_MAX_SUM_PER_PURCHASE // bond.ask.real_price)

    if existing_position:
        current_value = to_float(existing_position.quantity) * to_float(
            existing_position.current_price
        )
    else:
        current_value = 0.0

    waiter_reserved = sum(
        bond.at(o.price_percent).real_price * o.quantity
        for o in bid_registry.bids_for(bond.figi)
    )
    allowed_budget = settings.TOTAL_MAX_SUM_PER_BOND - current_value - waiter_reserved

    qty_by_shared_cap = 0
    if allowed_budget > 0:
        qty_by_shared_cap = int(allowed_budget // bond.ask.real_price)

    qty_by_balance = int(balance // bond.ask.real_price)

    qty = min(
        qty_by_purchase_cap,
        qty_by_shared_cap,
        qty_by_balance,
        bond.ask_quantity,
    )
    if qty == 0:
        log.info(
            "ask_skipped",
            name=bond.name,
            figi=bond.figi,
            ticker=bond.ticker,
            reason="zero_quantity",
            qty_by_purchase_cap=qty_by_purchase_cap,
            qty_by_shared_cap=qty_by_shared_cap,
            qty_by_balance=qty_by_balance,
            ask_quantity=bond.ask_quantity,
        )
    return qty


async def process_ask_sniper(ctx: MarketContext, bond: EnrichedBond) -> None:
    if ctx.cooldown_registry.on_cooldown(
        PurchaseStrategy.ASK_SNIPER, bond.figi, settings.ASK_COOLDOWN_SECONDS
    ):
        return

    if not _is_eligible_for_snipe(bond):
        return

    ask = bond.ask
    log.info(
        "ask_evaluating",
        name=bond.name,
        figi=bond.figi,
        ticker=bond.ticker,
        days_to_maturity=bond.days_to_maturity,
        annual_yield=ask.annual_yield,
        current_price=ask.current_price,
        aci_value=bond.aci_value,
        commission=ask.commission,
        real_price=ask.real_price,
        nominal=bond.nominal,
        coupons_sum=bond.coupons_sum,
        full_return=bond.full_return,
    )

    balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    if not balance.available:
        return

    existing_bonds = await fetch_bond_positions(ctx.client, ctx.account_id)
    existing_position = existing_bonds.get(bond.figi)

    quantity_to_buy = _compute_purchase_quantity(
        bond, balance.available, existing_position, ctx.bid_registry
    )

    if quantity_to_buy <= 0:
        return

    buy_price = await buy_at_ask(ctx.client, ctx.account_id, bond, quantity_to_buy)

    if buy_price is None:
        return

    # calculating total_buy_price using our commission here, instead of using commission
    # provided by response itself - because in response's commission is always 0,
    # broker itself calculates commission in separate operation
    total_buy_price = buy_price + (ask.commission * quantity_to_buy)
    log.info(
        "ask_purchased",
        name=bond.name,
        figi=bond.figi,
        ticker=bond.ticker,
        quantity=quantity_to_buy,
        total_price=total_buy_price,
        annual_yield=ask.annual_yield,
    )

    real_price_per_lot = total_buy_price / quantity_to_buy

    tmon_price = await fetch_tmon_etf_price_at(
        ctx.client, datetime.now(tz=timezone.utc)
    )
    ctx.purchase_repo.create(
        bond_name=bond.name,
        bond_figi=bond.figi,
        bond_ticker=bond.ticker,
        quantity=quantity_to_buy,
        nominal=bond.nominal,
        price=ask.current_price,
        aci_value=bond.aci_value,
        commission_percent=bond.commission_percent,
        real_price=real_price_per_lot,
        coupons_sum=bond.coupons_sum,
        risk_level=bond.risk_level,
        tmon_price=tmon_price,
        expected_maturity_date=bond.maturity_date,
        strategy=PurchaseStrategy.ASK_SNIPER,
    )
    ctx.cooldown_registry.mark(PurchaseStrategy.ASK_SNIPER, bond.figi)

    remaining_balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    message = compose_ask_snipe_notification(
        bond,
        quantity_to_buy,
        total_buy_price,
        remaining_balance.available,
        remaining_balance.reserved,
    )
    await notify(message)
