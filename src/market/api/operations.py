import logging
from datetime import datetime, timedelta, timezone

from t_tech.invest import Operation, OperationState, OperationType
from t_tech.invest.async_services import AsyncServices

logger = logging.getLogger(__name__)


async def fetch_operations(
    client: AsyncServices, account_id: str, since: datetime
) -> list[Operation]:
    response = await client.operations.get_operations(
        account_id=account_id,
        from_=since,
        to=datetime.now(tz=timezone.utc),
        state=OperationState.OPERATION_STATE_EXECUTED,
    )
    return response.operations


async def fetch_coupon_operation_for_repayment(
    client: AsyncServices,
    account_id: str,
    figi: str,
    repayment_date: datetime,
) -> Operation | None:
    response = await client.operations.get_operations(
        account_id=account_id,
        from_=repayment_date + timedelta(days=-1),  # type: ignore
        to=repayment_date + timedelta(days=1),
        state=OperationState.OPERATION_STATE_EXECUTED,
        figi=figi,
    )
    return next(
        (
            op
            for op in response.operations
            if op.operation_type == OperationType.OPERATION_TYPE_COUPON
        ),
        None,
    )
