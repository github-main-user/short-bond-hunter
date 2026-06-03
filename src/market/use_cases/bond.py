import logging
from datetime import datetime, timezone

from t_tech.invest import PortfolioPosition
from t_tech.invest.async_services import AsyncServices

from src.config import Settings, settings
from src.market.api import (
    buy_bond,
    fetch_account_balance_rub,
    fetch_existing_bonds,
    fetch_tmon_etf_price_at,
)
from src.market.domain import EnrichedBond
from src.market.messages import compose_purchase_notification
from src.market.utils import normalize_quotation
from src.stats import PurchaseRepository
from src.telegram import notify

logger = logging.getLogger(__name__)


def _is_bond_eligible_for_purchase(bond: EnrichedBond) -> bool:
    if bond.ticker in settings.BLACK_LIST_TICKERS:
        logger.info(f"Ineligible bond {bond.ticker}: bond is in the blacklist")
        return False

    if not (
        settings.ANNUAL_YIELD_MIN <= bond.annual_yield <= settings.ANNUAL_YIELD_MAX
    ):
        logger.info(
            f"Ineligible bond {bond.ticker}: annual yield "
            f"({bond.annual_yield:.2f}%) is not in the allowed range "
            f"({settings.ANNUAL_YIELD_MIN}%, {settings.ANNUAL_YIELD_MAX}%)"
        )
        return False

    if bond.real_price <= 0:
        logger.info(f"Ineligible bond {bond.ticker}: `real_price` is not positive")
        return False

    return True


def _compute_purchase_quantity(
    bond: EnrichedBond,
    balance: float,
    existing_position: PortfolioPosition | None,
    settings: Settings,
) -> int:
    quantity_to_buy_single = int(settings.BOND_SUM_MAX_SINGLE // bond.real_price)

    if existing_position:
        current_value = normalize_quotation(
            existing_position.quantity
        ) * normalize_quotation(existing_position.current_price)
        allowed_budget = settings.BOND_SUM_MAX - current_value
    else:
        allowed_budget = settings.BOND_SUM_MAX

    quantity_allowed_to_buy = 0
    if allowed_budget > 0:
        quantity_allowed_to_buy = int(allowed_budget // bond.real_price)

    quantity_available_to_buy = int(balance // bond.real_price)

    qty = min(
        quantity_to_buy_single,
        quantity_allowed_to_buy,
        quantity_available_to_buy,
        bond.ask_quantity,
    )
    if qty == 0:
        logger.info(
            f"{bond.ticker} quantity breakdown: "
            f"allowed_single={quantity_to_buy_single}, allowed_total={quantity_allowed_to_buy}, "
            f"balance={quantity_available_to_buy}, asks={bond.ask_quantity}"
        )
    return qty


async def process_bond(
    client: AsyncServices,
    bond: EnrichedBond,
    repo: PurchaseRepository,
    account_id: str,
) -> None:
    logger.info(
        f"Processing bond: {bond.ticker} ({bond.days_to_maturity}d, {bond.annual_yield:.2f}%) | "
        f"cost: {bond.current_price:.2f}₽ + {bond.aci_value:.2f}₽ + {bond.commission:.2f}₽ = {bond.real_price:.2f}₽ | "
        f"return: {bond.nominal:.2f}₽ + {bond.coupons_sum:.2f}₽ = {bond.full_return:.2f}₽"
    )

    if not _is_bond_eligible_for_purchase(bond):
        return

    balance = await fetch_account_balance_rub(client, account_id)
    if not balance:
        return

    existing_bonds = await fetch_existing_bonds(client, account_id)
    existing_position = existing_bonds.get(bond.ticker)

    quantity_to_buy = _compute_purchase_quantity(
        bond, balance, existing_position, settings
    )

    if quantity_to_buy <= 0:
        logger.info(
            f"Skipped bond {bond.ticker}: calculated quantity is {quantity_to_buy}"
        )
        return

    buy_price = await buy_bond(client, account_id, bond, quantity_to_buy)

    if buy_price is None:
        return

    # calculating real_buy_price using our commission here, instead of using commission
    # provided by response itself - because in response's commission is always 0,
    # broker itself calculates commission in separate operation
    real_buy_price = buy_price + (bond.commission * quantity_to_buy)

    tmon_price = await fetch_tmon_etf_price_at(client, datetime.now(tz=timezone.utc))
    repo.create(
        bond_name=bond.name,
        bond_figi=bond.figi,
        bond_ticker=bond.ticker,
        quantity=quantity_to_buy,
        nominal=bond.nominal,
        price=bond.current_price,
        aci_value=bond.aci_value,
        commission_percent=bond.commission_percent,
        real_price=real_buy_price / quantity_to_buy,
        coupons_sum=bond.coupons_sum,
        risk_level=bond.risk_level,
        tmon_price=tmon_price,
        expected_maturity_date=bond.maturity_date,
    )

    remaining_balance = await fetch_account_balance_rub(client, account_id)
    message = compose_purchase_notification(
        bond, quantity_to_buy, real_buy_price, remaining_balance
    )
    await notify(message)
