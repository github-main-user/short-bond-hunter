import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import override

from t_tech.invest import AsyncClient, Operation, OperationType
from t_tech.invest.schemas import OperationData, OperationsStreamRequest

from src.config import Settings
from src.market.api import fetch_operations
from src.market.domain import MaturityEvent, MaturityEventType
from src.market.utils import normalize_quotation

logger = logging.getLogger(__name__)


def _determine_event_type(operation_type: OperationType):
    event_type = None
    match operation_type:
        case OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL:
            event_type = MaturityEventType.REPAYMENT
        case OperationType.OPERATION_TYPE_COUPON:
            event_type = MaturityEventType.COUPON

    return event_type


class BaseMaturityProvider(ABC):
    def __init__(self, account_id: str, settings: Settings):
        self._account_id = account_id
        self._token = settings.TINVEST_TOKEN

    def _process_operation(self, operation: Operation | OperationData, is_missed: bool):
        op_type = (
            operation.operation_type
            if isinstance(operation, Operation)
            else operation.type
        )
        event_type = _determine_event_type(op_type)

        if not event_type:
            return None

        return MaturityEvent(
            event_type=event_type,
            bond_figi=operation.figi,
            payment=normalize_quotation(operation.payment),
            operation_date=operation.date,
            is_missed=is_missed,
        )

    @abstractmethod
    async def stream(self) -> AsyncGenerator[MaturityEvent]:
        yield  # type: ignore


class RealtimeMaturityProvider(BaseMaturityProvider):
    @override
    async def stream(self):
        logger.info("Subscribing to realtime maturity provider")
        async with AsyncClient(self._token) as client:
            request = OperationsStreamRequest(accounts=[self._account_id])
            async for response in client.operations_stream.operations_stream(request):
                if not response.operation:
                    continue

                event = self._process_operation(response.operation, is_missed=False)
                if event:
                    yield event


class DailyMissedMaturityProvider(BaseMaturityProvider):
    @override
    async def stream(self):
        while True:
            logger.info("Starting daily maturity fetch")
            async with AsyncClient(self._token) as client:
                since = datetime.now(tz=timezone.utc) - timedelta(days=2)
                operations = await fetch_operations(client, self._account_id, since)
                logger.info(f"Got {len(operations)} operations for past 2 days")

                for operation in operations:
                    event = self._process_operation(operation, is_missed=True)
                    if event:
                        yield event

            await asyncio.sleep(24 * 60 * 60)
