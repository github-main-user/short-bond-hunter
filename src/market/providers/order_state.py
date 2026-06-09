import logging
from collections.abc import AsyncGenerator

from t_tech.invest import AsyncClient
from t_tech.invest.schemas import (
    OrderStateStreamOrderState,
    OrderStateStreamRequest,
)

from src.config import Settings

logger = logging.getLogger(__name__)


class OrderStateProvider:
    def __init__(self, account_id: str, settings: Settings) -> None:
        self._account_id = account_id
        self._token = settings.TINVEST_TOKEN

    async def stream(self) -> AsyncGenerator[OrderStateStreamOrderState]:
        async with AsyncClient(self._token) as client:
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
