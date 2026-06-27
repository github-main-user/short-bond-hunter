import structlog
from datetime import datetime, timezone

from t_tech.invest.exceptions import AioRequestError
from t_tech.invest.grpc.schemas import (
    Bond,
    GetBondCouponsRequest,
    InstrumentIdType,
    InstrumentRequest,
)
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.market.utils import to_float

log = structlog.get_logger(__name__)


async def fetch_coupons_sum(
    client: AsyncServices, figi: str, maturity_date: datetime
) -> float:
    from_ = datetime.now(tz=timezone.utc)
    to = maturity_date

    if to < from_:
        log.warning(
            "skipping_coupons_fetch",
            reason="to_less_than_from",
            figi=figi,
            from_date=from_.isoformat(),
            to_date=to.isoformat(),
        )
        return 0.0

    coupon_resp = await client.instruments.get_bond_coupons(
        request=GetBondCouponsRequest(figi=figi, from_=from_, to=to)
    )
    return sum(to_float(c.pay_one_bond) for c in coupon_resp.events)


async def fetch_raw_bonds(client: AsyncServices) -> list[Bond]:
    response = await client.instruments.bonds()
    return response.instruments


async def fetch_bond_by_figi(client: AsyncServices, figi: str) -> Bond | None:
    try:
        response = await client.instruments.bond_by(
            request=InstrumentRequest(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                id=figi,
            )
        )
        return response.instrument
    except AioRequestError:
        log.info("bond_not_found_by_figi", figi=figi)
        return None
