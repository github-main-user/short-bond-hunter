import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from t_tech.invest import AsyncClient, OperationType
from t_tech.invest.schemas import OperationsStreamRequest

from market.api import fetch_bond_by_figi, fetch_operations
from market.utils import normalize_quotation
from src.market.api import fetch_bond_by_figi

logger = logging.getLogger(__name__)


class MaturityEventType(StrEnum):
    REPAYMENT = "REPAYMENT"
    COUPON = "COUPON"


@dataclass
class MaturityEvent:
    event_type: MaturityEventType
    bond_name: str
    bond_figi: str
    bond_ticker: str
    payment: float
    date: datetime
    is_missed: bool


def _determine_event_type(operation_type: OperationType):
    event_type = None
    match operation_type:
        case OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL:
            event_type = MaturityEventType.REPAYMENT
        case OperationType.OPERATION_TYPE_COUPON:
            event_type = MaturityEventType.COUPON

    return event_type


class RealtimeMaturityProvider:
    def __init__(self, token: str, account_id: str):
        self._token = token
        self._account_id = account_id

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
                    date=operation.date,
                    is_missed=False,
                )


class DailyMissedMaturityProvider:
    def __init__(self, token: str, account_id: str):
        self._token = token
        self._account_id = account_id

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
                        date=operation.date,
                        is_missed=True,
                    )

            await asyncio.sleep(24 * 60 * 60)
