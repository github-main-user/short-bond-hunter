import asyncio
import logging

from t_tech.invest.async_services import AsyncServices

from src.config import settings
from src.market.api import fetch_bonds, fetch_coupons_sum
from src.market.schemas import NBond
from src.market.utils import filter_bonds

logger = logging.getLogger(__name__)


async def get_tradable_bonds(client: AsyncServices) -> list[NBond]:
    bonds = await fetch_bonds(client)
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    coupon_sums = await asyncio.gather(
        *[fetch_coupons_sum(client, bond) for bond in bonds]
    )
    for bond, coupon_sum in zip(bonds, coupon_sums):
        bond.coupons_sum = coupon_sum

    return bonds
