import logging
from datetime import datetime, timezone

from t_tech.invest import AioRequestError, Bond, InstrumentIdType
from t_tech.invest.async_services import AsyncServices

from src.market.utils import to_float

logger = logging.getLogger(__name__)


async def fetch_coupons_sum(
    client: AsyncServices, figi: str, maturity_date: datetime
) -> float:
    from_ = datetime.now(tz=timezone.utc)
    to = maturity_date

    if to < from_:
        logger.warning("Skipping coupons fetch - `to` can't be less than `from`")
        return 0.0

    coupon_resp = await client.instruments.get_bond_coupons(
        figi=figi, from_=from_, to=to
    )
    return sum(to_float(c.pay_one_bond) for c in coupon_resp.events)


async def fetch_raw_bonds(client: AsyncServices) -> list[Bond]:
    response = await client.instruments.bonds()
    return response.instruments


async def fetch_bond_by_figi(client: AsyncServices, figi: str) -> Bond | None:
    try:
        response = await client.instruments.bond_by(
            id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
            id=figi,
        )
        return response.instrument
    except AioRequestError:
        logger.info(f"Got no bond by figi: {figi}")
        return None
