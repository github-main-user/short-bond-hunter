from collections.abc import AsyncGenerator

import structlog

from t_tech.invest.grpc import AsyncClient  # type: ignore
from t_tech.invest.grpc.schemas import (
    OrderStateStreamRequest,
    OrderStateStreamResponse,
)

from src.config import settings

log = structlog.get_logger(__name__)


class OrderStateProvider:
    def __init__(self, account_id: str) -> None:
        self._account_id = account_id

    async def stream(self) -> AsyncGenerator[OrderStateStreamResponse.OrderState]:
        async with AsyncClient(settings.TINVEST_TOKEN) as client:
            request = OrderStateStreamRequest(accounts=[self._account_id])
            log.info("order_state_stream_subscribed")
            async for response in client.orders_stream.order_state_stream(
                request=request
            ):
                if response.order_state is None:
                    continue
                yield response.order_state
