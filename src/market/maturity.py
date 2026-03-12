import asyncio
import logging
from datetime import datetime, timedelta, timezone

from t_tech.invest import AsyncClient, Operation, OperationType
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.schemas import OperationData, OperationsStreamRequest

from src.config import settings
from src.market.api import (
    fetch_coupon_for_repayment,
    fetch_maturity_operations,
    fetch_tmon_etf_price,
)
from src.market.messages import compose_maturity_notification
from src.market.utils import normalize_quotation
from src.stats.repository import StatsRepository
from src.telegram.services import send_telegram_message

logger = logging.getLogger(__name__)

_MISSED_MATURITIES_LOOKBACK_DAYS = 14


def _sum_maturity_payment(
    repayment: Operation | OperationData, coupon: Operation | None
) -> float:
    total = normalize_quotation(repayment.payment)
    if coupon is not None:
        total += normalize_quotation(coupon.payment)
    else:
        logger.warning(
            f"No coupon found for repayment {repayment.id} ({repayment.figi}), "
            "recording repayment amount only"
        )
    return total


async def _record_maturity(
    client: AsyncServices,
    stats_repo: StatsRepository,
    operation_id: str,
    figi: str,
    ticker: str,
    money_received: float,
    matured_at: datetime,
) -> None:
    tmon_price = await fetch_tmon_etf_price(client)
    if tmon_price is None:
        return
    stats_repo.save_maturity(
        operation_id, figi, ticker, tmon_price, money_received, matured_at
    )
    logger.info(f"Recorded maturity for {ticker} (op={operation_id})")

    message = compose_maturity_notification(ticker)
    logger.info(message)
    await send_telegram_message(message)


async def check_missed_maturities(
    client: AsyncServices, account_id: str, stats_repo: StatsRepository
) -> None:
    since = datetime.now(tz=timezone.utc) - timedelta(
        days=_MISSED_MATURITIES_LOOKBACK_DAYS
    )
    operations = await fetch_maturity_operations(client, account_id, since)

    repayments = [
        op
        for op in operations
        if op.operation_type == OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL
    ]
    coupons_by_instrument = {
        op.instrument_uid: op
        for op in operations
        if op.operation_type == OperationType.OPERATION_TYPE_COUPON
    }

    if not repayments:
        logger.info("No missed maturities found")
        return

    for repayment in repayments:
        if stats_repo.is_maturity_recorded(repayment.id):
            continue
        logger.info(f"Found unrecorded maturity: {repayment.figi} (op={repayment.id})")
        ticker = stats_repo.get_ticker_by_figi(repayment.figi)
        if ticker is None:
            logger.warning(
                f"Skipped recording maturity for {repayment.figi} "
                "(figi): related ticker not found"
            )
            continue
        coupon = coupons_by_instrument.get(repayment.instrument_uid)
        money_received = _sum_maturity_payment(repayment, coupon)
        await _record_maturity(
            client,
            stats_repo,
            repayment.id,
            repayment.figi,
            ticker,
            money_received,
            repayment.date,
        )


async def start_maturity_stream_session(
    account_id: str, stats_repo: StatsRepository
) -> None:
    while True:
        try:
            async with AsyncClient(settings.TINVEST_TOKEN) as client:
                logger.info("Subscribing to operations stream")
                request = OperationsStreamRequest(accounts=[account_id])
                async for response in client.operations_stream.operations_stream(
                    request
                ):
                    if not response.operation:
                        continue
                    op = response.operation
                    if op.type != OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL:
                        continue
                    if stats_repo.is_maturity_recorded(op.id):
                        continue
                    logger.info(
                        f"Maturity event received: {op.figi} / {op.ticker} (op={op.id})"
                    )
                    coupon = await fetch_coupon_for_repayment(
                        client, account_id, op.instrument_uid, op.date
                    )
                    money_received = _sum_maturity_payment(op, coupon)
                    await _record_maturity(
                        client,
                        stats_repo,
                        op.id,
                        op.figi,
                        op.ticker,
                        money_received,
                        op.date,
                    )
        except Exception as e:
            logger.error(f"Unexpected error in maturity stream: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)
