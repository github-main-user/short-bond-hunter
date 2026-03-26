import logging
from datetime import datetime, timezone

from t_tech.invest.async_services import AsyncServices

from src.config import settings
from src.market.api import (
    buy_bond,
    fetch_account_balance,
    fetch_existing_bonds,
    fetch_tmon_etf_price_at,
)
from src.market.messages import compose_purchase_notification
from src.market.schemas import NBond
from src.market.utils import normalize_quotation
from src.stats.repository import StatsRepository
from src.telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def _is_bond_eligible_for_purchase(bond: NBond) -> bool:
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


async def _calculate_purchase_quantity(
    client: AsyncServices, bond: NBond, account_id: str
) -> int:
    balance = await fetch_account_balance(client, account_id)
    existing_bonds = await fetch_existing_bonds(client, account_id)
    existing_bond = existing_bonds.get(bond.ticker)

    quantity_to_buy_single = int(settings.BOND_SUM_MAX_SINGLE // bond.real_price)

    if existing_bond:
        current_value = normalize_quotation(
            existing_bond.quantity
        ) * normalize_quotation(existing_bond.current_price)
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
            f"single={quantity_to_buy_single}, allowed={quantity_allowed_to_buy}, "
            f"available={quantity_available_to_buy}, ask={bond.ask_quantity}"
        )
    return qty


async def process_bond_for_purchase(
    client: AsyncServices, bond: NBond, stats_repo: StatsRepository, account_id: str
) -> None:
    logger.info(
        f"Processing bond: {bond.ticker} ({bond.days_to_maturity}d, {bond.annual_yield:.2f}%) | "
        f"return: {bond.nominal:.2f}₽ + {bond.coupons_sum:.2f}₽ = {bond.full_return:.2f}₽ | "
        f"cost: {bond.current_price:.2f}₽ + {bond.aci_value:.2f}₽ + {bond.commission:.2f}₽ = {bond.real_price:.2f}₽"
    )

    if not _is_bond_eligible_for_purchase(bond):
        return

    quantity_to_buy = await _calculate_purchase_quantity(client, bond, account_id)

    if quantity_to_buy <= 0:
        logger.info(
            f"Skipped bond {bond.ticker}: calculated quantity is {quantity_to_buy}"
        )
        return

    buy_price = await buy_bond(client, account_id, bond, quantity_to_buy)

    if buy_price is None:
        return

    # calculating real_buy_price here, instead of using commission provided by api
    # itself - because in provided by api field commission is always 0 by some reason.
    real_buy_price = buy_price + (bond.commission * quantity_to_buy)

    message = compose_purchase_notification(bond, quantity_to_buy, real_buy_price)
    logger.info(message)
    await send_telegram_message(message)

    tmon_price = await fetch_tmon_etf_price_at(client, datetime.now(tz=timezone.utc))
    stats_repo.save_purchase(
        bond, quantity_to_buy, real_buy_price / quantity_to_buy, tmon_price
    )
