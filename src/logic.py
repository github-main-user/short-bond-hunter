import logging

from .config import settings
from .market.services import fetch_bonds, update_market_data
from .market.utils import filter_bonds
from .telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def logic() -> None:
    bonds = fetch_bonds()
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    for bond in bonds:
        try:
            update_market_data(fee_percent=settings.FEE_PERCENT, bond=bond)
        except Exception as e:
            logger.error(f"Got an exception: %s", e)

        if not bond.market_data:
            return

        if (
            settings.ANNUAL_YIELD_MIN
            <= bond.market_data.annual_yield
            <= settings.ANNUAL_YIELD_MAX
        ):
            send_telegram_message(
                f"Bond `{bond.ticker}` has annual yeild {bond.market_data.annual_yield}%"
            )
