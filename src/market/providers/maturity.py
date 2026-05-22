import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from t_tech.invest import AsyncClient, OperationType

from src.config import Settings
from src.market.api import fetch_operations
from src.market.domain import MaturityEvent, MaturityEventType
from src.market.utils import normalize_quotation

logger = logging.getLogger(__name__)


_OPERATION_TYPE_MAP = {
    OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL: MaturityEventType.REPAYMENT,
    OperationType.OPERATION_TYPE_COUPON: MaturityEventType.COUPON,
}

_HOUR_IN_SECONDS = 60 * 60


class MaturityProvider:
    def __init__(self, account_id: str, settings: Settings):
        self._account_id = account_id
        self._token = settings.TINVEST_TOKEN

    async def stream(self) -> AsyncGenerator[MaturityEvent]:
        while True:
            logger.info("Starting hourly maturity fetch")
            async with AsyncClient(self._token) as client:
                since = datetime.now(tz=timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                operations = await fetch_operations(client, self._account_id, since)
                logger.info(f"Got {len(operations)} operations for past 2 days")

                for operation in operations:
                    event_type = _OPERATION_TYPE_MAP.get(operation.operation_type)
                    if event_type is None:
                        continue

                    yield MaturityEvent(
                        event_type=event_type,
                        bond_figi=operation.figi,
                        payment=normalize_quotation(operation.payment),
                        operation_date=operation.date,
                    )

            await asyncio.sleep(_HOUR_IN_SECONDS)
