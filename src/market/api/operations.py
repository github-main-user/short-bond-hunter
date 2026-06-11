import logging
from datetime import datetime, timezone

from t_tech.invest import Operation, OperationState
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
