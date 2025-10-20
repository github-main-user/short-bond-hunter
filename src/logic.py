import logging

from .market.services import fetch_bonds, update_market_data
from .market.utils import filter_bonds
from .telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def logic() -> None:
    bonds = fetch_bonds()
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=30)
    logger.info("%s bonds left after filtration", len(bonds))

    for bond in bonds:
        try:
            update_market_data(fee_percent=0.05, bond=bond)
        except Exception as e:
            logger.error(f"Got an exception: %s", e)

    for bond in bonds:
        if bond.market_data and bond.market_data.annual_yield >= 20:
            message = (
                f"Bond {bond.ticker} has annual yeild {bond.market_data.annual_yield}%"
            )
            send_telegram_message(message)
