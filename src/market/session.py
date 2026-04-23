import asyncio
import logging

from t_tech.invest import AsyncClient, OperationType
from t_tech.invest.schemas import OperationsStreamRequest

from src.config import settings
from src.market.api import fetch_account_id
from src.market.maturity import (
    check_missed_maturities,
    process_coupon_for_maturity,
    process_maturity_repayment,
)
from src.stats import StatsRepository

logger = logging.getLogger(__name__)


async def _with_retry(fn, *args, **kwargs) -> None:
    while True:
        try:
            await fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unexpected error in {fn.__name__}: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)


async def _maturity_stream_iteration(
    account_id: str, stats_repo: StatsRepository
) -> None:
    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        request = OperationsStreamRequest(accounts=[account_id])
        async for response in client.operations_stream.operations_stream(request):
            if not response.operation:
                continue
            operation = response.operation

            match operation.type:
                case OperationType.OPERATION_TYPE_COUPON:
                    await process_coupon_for_maturity(
                        stats_repo, operation.figi, operation.payment
                    )
                case OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL:
                    if stats_repo.is_maturity_recorded(operation.parent_operation_id):
                        continue

                    logger.info(
                        f"Maturity event received:"
                        f" {operation.figi} / {operation.ticker}"
                        f" (op={operation.parent_operation_id})"
                    )

                    await process_maturity_repayment(
                        client,
                        stats_repo,
                        account_id,
                        operation.parent_operation_id,
                        operation,
                        is_missed=False,
                    )


async def start_market_streaming_session() -> None:
    stats_repo = StatsRepository()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)
        await check_missed_maturities(client, account_id, stats_repo)

    await asyncio.gather(
        _with_retry(_maturity_stream_iteration, account_id, stats_repo),
    )
