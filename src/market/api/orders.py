import logging
from typing import TYPE_CHECKING

from t_tech.invest import (
    OrderDirection,
    OrderExecutionReportStatus,
    OrderType,
    PriceType,
    TimeInForceType,
)
from t_tech.invest.async_services import AsyncServices

from src.market.utils import normalize_quotation

if TYPE_CHECKING:
    from src.market.domain import EnrichedBond

logger = logging.getLogger(__name__)


async def buy_bond(
    client: AsyncServices, account_id: str, bond: "EnrichedBond", quantity: int
) -> float | None:

    response = await client.orders.post_order(
        account_id=account_id,
        figi=bond.figi,
        quantity=quantity,
        price=bond.orderbook.asks[0].price,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_LIMIT,
        time_in_force=TimeInForceType.TIME_IN_FORCE_FILL_OR_KILL,
        price_type=PriceType.PRICE_TYPE_POINT,
    )
    if (
        response.execution_report_status
        != OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
    ):
        logger.warning(
            f"Order for {bond.ticker} was not filled"
            f" (status: {response.execution_report_status})"
        )
        return None
    return normalize_quotation(response.total_order_amount) * bond.nominal / 100
