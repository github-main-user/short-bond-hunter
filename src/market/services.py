import asyncio
import logging

from t_tech.invest import OrderBook
from t_tech.invest.async_services import AsyncServices

from src.config import settings
from src.market.api import fetch_coupons_sum, fetch_raw_bonds, fetch_user_commission
from src.market.schemas import NBond
from src.market.utils import filter_bonds

logger = logging.getLogger(__name__)


async def get_tradable_bonds(client: AsyncServices) -> list[NBond]:
    user_commission = await fetch_user_commission(client)
    raw_bonds = await fetch_raw_bonds(client)
    logger.info(f"Got {len(raw_bonds)} bonds")

    filtered = filter_bonds(raw_bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info(f"{len(filtered)} bonds left after filtering")

    coupon_sums = await asyncio.gather(
        *[fetch_coupons_sum(client, bond.figi, bond.maturity_date) for bond in filtered]
    )

    return [
        NBond.from_bond(
            bond,
            commission_percent=user_commission,
            coupons_sum=coupon_sum,
            orderbook=OrderBook(figi=bond.figi, asks=[]),
        )
        for bond, coupon_sum in zip(filtered, coupon_sums)
    ]
