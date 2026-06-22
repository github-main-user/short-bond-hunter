import logging
from collections.abc import AsyncGenerator

from t_tech.invest.grpc import AsyncClient  # type: ignore
from t_tech.invest.grpc.schemas import (
    OrderStateStreamRequest,
    OrderStateStreamResponse,
)

from src.config import settings

logger = logging.getLogger(__name__)


class OrderStateProvider:
    def __init__(self, account_id: str) -> None:
        self._account_id = account_id

    async def stream(self) -> AsyncGenerator[OrderStateStreamResponse.OrderState]:
        async with AsyncClient(settings.TINVEST_TOKEN) as client:
            request = OrderStateStreamRequest(accounts=[self._account_id])
            logger.info(
                f"Subscribed to order state stream for account {self._account_id}"
            )
            async for response in client.orders_stream.order_state_stream(
                request=request
            ):
                if response.order_state is None:
                    continue
                yield response.order_state
