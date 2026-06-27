import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import structlog

from t_tech.invest.grpc import AsyncClient  # type: ignore
from t_tech.invest.grpc.schemas import OperationType

from src.config import settings
from src.market.api import fetch_operations
from src.market.domain import MaturityEvent, MaturityEventType
from src.market.utils import to_float

log = structlog.get_logger(__name__)


_OPERATION_TYPE_MAP = {
    OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL: MaturityEventType.REPAYMENT,
    OperationType.OPERATION_TYPE_COUPON: MaturityEventType.COUPON,
}

_HOUR_IN_SECONDS = 60 * 60


class MaturityProvider:
    def __init__(self, account_id: str):
        self._account_id = account_id

    async def stream(self) -> AsyncGenerator[MaturityEvent]:
        while True:
            log.debug("maturity_fetch_started")
            async with AsyncClient(settings.TINVEST_TOKEN) as client:
                since = datetime.now(tz=timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                operations = await fetch_operations(client, self._account_id, since)
                log.debug("operations_fetched", count=len(operations))

                for operation in operations:
                    event_type = _OPERATION_TYPE_MAP.get(operation.operation_type)
                    if event_type is None:
                        continue

                    yield MaturityEvent(
                        event_type=event_type,
                        bond_figi=operation.figi,
                        payment=to_float(operation.payment),
                        operation_date=operation.date,
                    )

            await asyncio.sleep(_HOUR_IN_SECONDS)
