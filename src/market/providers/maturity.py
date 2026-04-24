import asyncio
import logging
from datetime import datetime, timedelta, timezone

from t_tech.invest import AsyncClient, OperationType
from t_tech.invest.schemas import OperationsStreamRequest

from config import Settings
from src.market.api import fetch_bond_by_figi, fetch_operations
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


class RealtimeMaturityProvider:
    def __init__(self, account_id: str, settings: Settings):
        self._account_id = account_id
        self._token = settings.TINVEST_TOKEN

    async def stream(self):
        async with AsyncClient(self._token) as client:
            request = OperationsStreamRequest(accounts=[self._account_id])
            async for response in client.operations_stream.operations_stream(request):
                if not response.operation:
                    continue
                operation = response.operation

                event_type = _determine_event_type(operation.type)

                if not event_type:
                    continue

                yield MaturityEvent(
                    event_type=event_type,
                    bond_name=operation.name,
                    bond_figi=operation.figi,
                    bond_ticker=operation.ticker,
                    payment=normalize_quotation(operation.payment),
                    operation_date=operation.date,
                    is_missed=False,
                )


class DailyMissedMaturityProvider:
    def __init__(self, account_id: str, settings: Settings):
        self._account_id = account_id
        self._token = settings.TINVEST_TOKEN

    async def stream(self):
        while True:
            async with AsyncClient(self._token) as client:
                since = datetime.now(tz=timezone.utc) - timedelta(days=2)
                operations = await fetch_operations(client, self._account_id, since)

                if not operations:
                    logger.info("No missed maturities found")

                for operation in operations:
                    event_type = _determine_event_type(operation.operation_type)

                    if not event_type:
                        continue

                    bond = await fetch_bond_by_figi(client, operation.figi)
                    if not bond:
                        continue

                    yield MaturityEvent(
                        event_type=event_type,
                        bond_name=bond.name,
                        bond_figi=operation.figi,
                        bond_ticker=bond.ticker,
                        payment=normalize_quotation(operation.payment),
                        operation_date=operation.date,
                        is_missed=True,
                    )

            await asyncio.sleep(24 * 60 * 60)
