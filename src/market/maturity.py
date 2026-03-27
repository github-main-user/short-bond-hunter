import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiohttp import ClientResponseError
from t_tech.invest import AsyncClient, Operation, OperationType
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.schemas import OperationData, OperationsStreamRequest

from src.config import settings
from src.market.api import (
    fetch_bond_by_figi,
    fetch_coupon_for_repayment,
    fetch_repayment_operations,
    fetch_tmon_etf_price_at,
)
from src.market.messages import compose_maturity_notification
from src.market.utils import normalize_quotation
from src.stats import StatsRepository
from src.telegram import TelegramNotConfiguredError, send_telegram_message

logger = logging.getLogger(__name__)

_MISSED_REPAYMENTS_LOOKBACK_DAYS = 14


def _sum_maturity_payment(
    repayment: Operation | OperationData, coupon: Operation | None
) -> float:
    total = normalize_quotation(repayment.payment)
    if coupon is not None:
        total += normalize_quotation(coupon.payment)
    else:
        logger.warning(
            f"No coupon found for repayment ({repayment.figi}), "
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
    tmon_price = await fetch_tmon_etf_price_at(client, matured_at)
    stats_repo.save_maturity(
        operation_id, figi, ticker, tmon_price, money_received, matured_at
    )
    logger.info(f"Recorded maturity for {ticker} (op={operation_id})")

    message = compose_maturity_notification(ticker, money_received)
    logger.info(message)
    try:
        await send_telegram_message(message)
    except (TelegramNotConfiguredError, ClientResponseError) as e:
        logger.warning(f"Failed to send telegram message: {e}")


async def check_missed_maturities(
    client: AsyncServices, account_id: str, stats_repo: StatsRepository
) -> None:
    since = datetime.now(tz=timezone.utc) - timedelta(
        days=_MISSED_REPAYMENTS_LOOKBACK_DAYS
    )
    repayments = await fetch_repayment_operations(client, account_id, since)

    if not repayments:
        logger.info("No missed maturities found")
        return

    for repayment in repayments:
        if stats_repo.is_maturity_recorded(repayment.id):
            continue
        logger.info(f"Found unrecorded maturity: {repayment.figi} (op={repayment.id})")

        bond = await fetch_bond_by_figi(client, repayment.figi)
        if bond is None:
            logger.warning(
                f"Skipped recording maturity for {repayment.figi} "
                "(figi): bond not found"
            )
            continue

        coupon = await fetch_coupon_for_repayment(
            client, account_id, repayment.instrument_uid, repayment.date
        )
        money_received = _sum_maturity_payment(repayment, coupon)
        await _record_maturity(
            client,
            stats_repo,
            repayment.id,
            repayment.figi,
            bond.ticker,
            money_received,
            bond.maturity_date,
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
                    repayment = response.operation
                    if (
                        repayment.type
                        != OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL
                    ):
                        continue
                    if stats_repo.is_maturity_recorded(repayment.parent_operation_id):
                        continue
                    logger.info(
                        f"Maturity event received: "
                        f"{repayment.figi} / {repayment.ticker} (op={repayment.parent_operation_id})"
                    )
                    bond = await fetch_bond_by_figi(client, repayment.figi)
                    if bond is None:
                        logger.warning(
                            f"Skipped recording maturity for {repayment.figi} (figi): "
                            "bond not found"
                        )
                        continue
                    coupon = await fetch_coupon_for_repayment(
                        client, account_id, repayment.instrument_uid, repayment.date
                    )
                    money_received = _sum_maturity_payment(repayment, coupon)
                    await _record_maturity(
                        client,
                        stats_repo,
                        repayment.parent_operation_id,
                        repayment.figi,
                        bond.ticker,
                        money_received,
                        bond.maturity_date,
                    )
        except Exception as e:
            logger.error(f"Unexpected error in maturity stream: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)
