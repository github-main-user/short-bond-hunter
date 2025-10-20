import logging

from .config import settings
from .market.services import (
    buy_bond,
    fetch_bonds,
    get_account_balance,
    get_account_id,
    update_market_data,
)
from .market.utils import filter_bonds
from .telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def logic() -> None:
    bonds = fetch_bonds()
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    max_annual_yield = 0

    for bond in bonds:
        logger.info("Processing bond: %s", bond.ticker)

        try:
            update_market_data(fee_percent=settings.FEE_PERCENT, bond=bond)
        except Exception as e:
            logger.error("Got an exception: %s", e)

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
                f"Trying to buy bond: `%s` (%s%%) (%s bonds for current: %s₽ + real: %s₽)",
                bond.ticker,
                format(bond.market_data.annual_yield, ".2f"),
                bond.market_data.ask_quantity,
                format(bond.market_data.current_price, ".2f"),
                format(bond.market_data.real_price, ".2f"),
            )
            account_id = get_account_id()
            balance = get_account_balance(account_id)
            try:
                if balance >= bond.market_data.real_price:
                    buy_price = buy_bond(account_id, bond, 1)

                    message = f"Bought 1 {bond.ticker} for {buy_price + bond.market_data.fee:.2f}₽"
                    logger.info(message)
                else:
                    message = f"Cannot buy {bond.ticker} - Not enought balance"
                    logger.warning(message)

                send_telegram_message(message)
            except Exception as e:
                logger.error("Error ocured during order post %s", e)

    logger.info("Maximum annual yield: %s%%", format(max_annual_yield, ".2f"))
