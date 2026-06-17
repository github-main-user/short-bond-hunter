import logging
from datetime import datetime, timezone

from t_tech.invest import PortfolioPosition

from src.config import settings
from src.market.api import (
    buy_at_ask,
    fetch_account_balance_rub,
    fetch_bond_positions,
    fetch_tmon_etf_price_at,
)
from src.market.context import MarketContext
from src.market.domain import EnrichedBond
from src.market.messages import compose_ask_snipe_notification
from src.market.utils import to_float
from src.stats.models import PurchaseStrategy
from src.telegram import notify

logger = logging.getLogger(__name__)


def _is_eligible_for_snipe(bond: EnrichedBond) -> bool:
    if bond.ticker in settings.BLACK_LIST_TICKERS:
        logger.debug(f"Ineligible bond {bond.ticker}: bond is in the blacklist")
        return False

    if not (
        settings.ASK_MIN_ANNUAL_YIELD
        <= bond.ask.annual_yield
        <= settings.ASK_MAX_ANNUAL_YIELD
    ):
        logger.debug(
            f"Ineligible bond {bond.ticker}: annual yield "
            f"({bond.ask.annual_yield:.2f}%) is not in the allowed range "
            f"[{settings.ASK_MIN_ANNUAL_YIELD}%, {settings.ASK_MAX_ANNUAL_YIELD}%]"
        )
        return False

    if bond.ask.real_price <= 0:
        logger.debug(f"Ineligible bond {bond.ticker}: ask real price is not positive")
        return False

    return True


def _compute_purchase_quantity(
    bond: EnrichedBond,
    balance: float,
    existing_position: PortfolioPosition | None,
) -> int:
    qty_by_purchase_cap = int(settings.ASK_MAX_SUM_PER_PURCHASE // bond.ask.real_price)

    if existing_position:
        current_value = to_float(
            existing_position.quantity
        ) * to_float(existing_position.current_price)
    else:
        current_value = 0.0

    allowed_budget = settings.ASK_MAX_SUM_PER_BOND - current_value

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
        logger.info(
            f"Skipped {bond.ticker}: quantity is 0 "
            f"(by_purchase_cap={qty_by_purchase_cap}, by_shared_cap={qty_by_shared_cap}, "
            f"by_balance={qty_by_balance}, asks={bond.ask_quantity})"
        )
    return qty


async def process_ask_sniper(ctx: MarketContext, bond: EnrichedBond) -> None:
    if not _is_eligible_for_snipe(bond):
        return

    ask = bond.ask
    logger.info(
        f"Processing {bond.ticker} ({bond.days_to_maturity}d, {ask.annual_yield:.2f}%) | "
        f"cost: {ask.current_price:.2f}₽ + {bond.aci_value:.2f}₽ + {ask.commission:.2f}₽ = {ask.real_price:.2f}₽ | "
        f"return: {bond.nominal:.2f}₽ + {bond.coupons_sum:.2f}₽ = {bond.full_return:.2f}₽"
    )

    balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    if not balance:
        return

    existing_bonds = await fetch_bond_positions(ctx.client, ctx.account_id)
    existing_position = existing_bonds.get(bond.figi)

    quantity_to_buy = _compute_purchase_quantity(bond, balance, existing_position)

    if quantity_to_buy <= 0:
        return

    buy_price = await buy_at_ask(ctx.client, ctx.account_id, bond, quantity_to_buy)

    if buy_price is None:
        return

    # calculating real_buy_price using our commission here, instead of using commission
    # provided by response itself - because in response's commission is always 0,
    # broker itself calculates commission in separate operation
    real_buy_price = buy_price + (ask.commission * quantity_to_buy)

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
        real_price=real_buy_price / quantity_to_buy,
        coupons_sum=bond.coupons_sum,
        risk_level=bond.risk_level,
        tmon_price=tmon_price,
        expected_maturity_date=bond.maturity_date,
        strategy=PurchaseStrategy.ASK_SNIPER,
    )

    remaining_balance = await fetch_account_balance_rub(ctx.client, ctx.account_id)
    message = compose_ask_snipe_notification(
        bond, quantity_to_buy, real_buy_price, remaining_balance
    )
    await notify(message)
