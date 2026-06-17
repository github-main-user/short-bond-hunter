import logging
import uuid
from typing import TYPE_CHECKING

from t_tech.invest import (
    AioRequestError,
    OrderDirection,
    OrderExecutionReportStatus,
    OrderState,
    OrderType,
    PostOrderResponse,
    PriceType,
    ReplaceOrderRequest,
    TimeInForceType,
)
from t_tech.invest.async_services import AsyncServices

from src.market.api.order_errors import handle_order_error
from src.market.utils import from_float, to_float

if TYPE_CHECKING:
    from src.market.domain import EnrichedBond

logger = logging.getLogger(__name__)


_ACCEPTED_ORDER_STATUSES = {
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_NEW,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL,
}

_RESTING_ORDER_STATUSES = {
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_NEW,
    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_PARTIALLYFILL,
}


async def buy_at_ask(
    client: AsyncServices, account_id: str, bond: "EnrichedBond", quantity: int
) -> float | None:

    try:
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
    except AioRequestError as e:
        handle_order_error(e, f"Ask buy for {bond.ticker}")
        return None
    if (
        response.execution_report_status
        != OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_FILL
    ):
        logger.warning(
            f"Order for {bond.ticker} was not filled"
            f" (status: {response.execution_report_status})"
        )
        return None
    return to_float(response.total_order_amount) * bond.nominal / 100


async def place_bid_order(
    client: AsyncServices,
    account_id: str,
    bond: "EnrichedBond",
    quantity: int,
    price_percent: float,
) -> PostOrderResponse | None:
    try:
        response = await client.orders.post_order(
            account_id=account_id,
            figi=bond.figi,
            quantity=quantity,
            price=from_float(price_percent),
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=OrderType.ORDER_TYPE_LIMIT,
            time_in_force=TimeInForceType.TIME_IN_FORCE_DAY,
            price_type=PriceType.PRICE_TYPE_POINT,
        )
    except AioRequestError as e:
        handle_order_error(e, f"Bid for {bond.ticker}")
        return None
    if response.execution_report_status not in _ACCEPTED_ORDER_STATUSES:
        logger.warning(
            f"Bid for {bond.ticker} was not accepted"
            f" (status: {response.execution_report_status})"
        )
        return None
    return response


async def replace_bid_order(
    client: AsyncServices,
    account_id: str,
    bond: "EnrichedBond",
    old_order_id: str,
    quantity: int,
    price_percent: float,
) -> PostOrderResponse | None:
    context = f"Replace of bid {old_order_id} for {bond.ticker}"
    try:
        response = await client.orders.replace_order(
            ReplaceOrderRequest(
                account_id=account_id,
                order_id=old_order_id,
                idempotency_key=str(uuid.uuid4()),
                quantity=quantity,
                price=from_float(price_percent),
                price_type=PriceType.PRICE_TYPE_POINT,
            )
        )
    except AioRequestError as e:
        handle_order_error(e, context)
        return None
    if response.execution_report_status not in _ACCEPTED_ORDER_STATUSES:
        logger.warning(
            f"{context} was not accepted"
            f" (status: {response.execution_report_status})"
        )
        return None
    return response


async def cancel_bid_order(
    client: AsyncServices, account_id: str, order_id: str
) -> None:
    try:
        await client.orders.cancel_order(account_id=account_id, order_id=order_id)
    except AioRequestError as e:
        handle_order_error(e, f"Cancel of bid {order_id}")


async def fetch_active_bid_orders(
    client: AsyncServices, account_id: str
) -> list[OrderState]:
    response = await client.orders.get_orders(account_id=account_id)
    return [
        order
        for order in response.orders
        if order.execution_report_status in _RESTING_ORDER_STATUSES
        and order.direction == OrderDirection.ORDER_DIRECTION_BUY
        and order.order_type == OrderType.ORDER_TYPE_LIMIT
    ]
