import logging

from src.config import settings
from src.market.services import (
    buy_bond,
    fetch_bonds,
    get_account_balance,
    get_account_id,
    get_existing_bonds,
    update_market_data,
)
from src.market.utils import filter_bonds, normalize_quotation
from src.telegram.services import send_telegram_message

logger = logging.getLogger(__name__)

BONDS = []


def update_bonds() -> None:
    global BONDS
    bonds = fetch_bonds()
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    BONDS = bonds


def trading_logic() -> None:
    max_annual_yield = 0
    for bond in BONDS:
        logger.info("Processing bond: %s", bond.ticker)

        try:
            update_market_data(fee_percent=settings.FEE_PERCENT, bond=bond)
        except Exception as e:
            logger.error("Got an exception during market data update: %s", e)

        if not bond.market_data:
            logger.info("Skipped bond: %s - No market data", bond.ticker)
            continue

        max_annual_yield = max(max_annual_yield, bond.market_data.annual_yield)

        if (
            settings.ANNUAL_YIELD_MIN
            <= bond.market_data.annual_yield
            <= settings.ANNUAL_YIELD_MAX
        ):
            logger.info(
                f"Trying to buy bond: `%s` (%s%%) (%s bonds for current: %s₽, real: %s₽)",
                bond.ticker,
                format(bond.market_data.annual_yield, ".2f"),
                bond.market_data.ask_quantity,
                format(bond.market_data.current_price, ".2f"),
                format(bond.market_data.real_price, ".2f"),
            )
            if bond.market_data.real_price <= 0:
                logger.info(
                    "Skipped bond: %s - real_price is not positive.", bond.ticker
                )
                continue

            account_id = get_account_id()
            balance = get_account_balance(account_id)
            existing_bond = get_existing_bonds(account_id).get(bond.ticker)

            quantity_to_buy_single = int(
                settings.BOND_SUM_MAX_SINGLE // bond.market_data.real_price
            )

            if existing_bond:
                current_value = normalize_quotation(
                    existing_bond.quantity
                ) * normalize_quotation(existing_bond.current_price)
                allowed_budget = settings.BOND_SUM_MAX - current_value
            else:
                allowed_budget = settings.BOND_SUM_MAX

            quantity_allowed_to_buy = 0
            if allowed_budget > 0:
                quantity_allowed_to_buy = int(
                    allowed_budget // bond.market_data.real_price
                )

            quantity_available_to_buy = int(balance // bond.market_data.real_price)

            quantity_to_buy = min(
                quantity_to_buy_single,
                quantity_allowed_to_buy,
                quantity_available_to_buy,
                bond.market_data.ask_quantity,
            )

            if quantity_to_buy > 0:
                try:
                    buy_price = buy_bond(account_id, bond, quantity_to_buy)
                except Exception as e:
                    logger.error("Error occurred during order post %s", e)
                else:
                    real_buy_price = buy_price + bond.market_data.fee
                    message = (
                        f"Bought {quantity_to_buy} of {bond.ticker} ({bond.market_data.annual_yield:.2f}%)\n"
                        f"Available: {bond.market_data.ask_quantity}\n"
                        f"Expected price: {bond.market_data.real_price * quantity_to_buy:.2f}₽\n"
                        f"Actual price: {real_buy_price:.2f}₽\n"
                        f"Benefit: {bond.market_data.benefit:.2f}₽ in {bond.days_to_maturity} days ({bond.market_data.benefit / bond.days_to_maturity:.2f}₽ per day)"
                    )
                    logger.info(message)
                    send_telegram_message(message)
            else:
                logger.info(
                    "Skipped buying %s: calculated quantity is %s",
                    bond.ticker,
                    quantity_to_buy,
                )

    logger.info("Maximum annual yield: %s%%", format(max_annual_yield, ".2f"))
