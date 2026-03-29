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
    fetch_coupon_operation_for_repayment,
    fetch_repayment_operations,
    fetch_tmon_etf_price_at,
)
from src.market.messages import compose_maturity_notification
from src.market.utils import normalize_quotation
from src.stats import StatsRepository
from src.telegram import TelegramNotConfiguredError, send_telegram_message

logger = logging.getLogger(__name__)


async def _process_maturity_repayment(
    client: AsyncServices,
    stats_repo: StatsRepository,
    account_id: str,
    operation_id: str,
    repayment: Operation | OperationData,
) -> None:
    money_received = normalize_quotation(repayment.payment)

    bond = await fetch_bond_by_figi(client, repayment.figi)
    if bond is None:
        logger.warning(
            f"Skipped recording maturity for {repayment.figi} (figi): bond not found"
        )
        return

    coupon = await fetch_coupon_operation_for_repayment(
        client, account_id, repayment.instrument_uid, repayment.date
    )
    if coupon is not None:
        money_received += normalize_quotation(coupon.payment)
    else:
        logger.warning(f"No coupon operation found for repayment: {operation_id}")

    tmon_price_at_maturity = await fetch_tmon_etf_price_at(client, bond.maturity_date)
    tmon_price_at_money_received = await fetch_tmon_etf_price_at(client, repayment.date)

    stats_repo.save_maturity(
        operation_id,
        repayment.figi,
        bond.ticker,
        tmon_price_at_maturity,
        tmon_price_at_money_received,
        money_received,
        bond.maturity_date,
        repayment.date,
    )
    logger.info(f"Recorded maturity for {bond.ticker} (op={operation_id})")

    message = compose_maturity_notification(bond.ticker, money_received)
    logger.info(message)
    try:
        await send_telegram_message(message)
    except (TelegramNotConfiguredError, ClientResponseError) as e:
        logger.error(f"Failed to send telegram message: {e}")


async def check_missed_maturities(
    client: AsyncServices, account_id: str, stats_repo: StatsRepository
) -> None:
    since = datetime.now(tz=timezone.utc) - timedelta(
        days=settings.MISSED_REPAYMENTS_LOOKBACK_DAYS
    )
    repayments = await fetch_repayment_operations(client, account_id, since)

    if not repayments:
        logger.info("No missed maturities found")
        return

    for repayment in repayments:
        if stats_repo.is_maturity_recorded(repayment.id):
            continue
        logger.info(f"Found unrecorded maturity: {repayment.figi} (op={repayment.id})")
        await _process_maturity_repayment(
            client, stats_repo, account_id, repayment.id, repayment
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
                    await _process_maturity_repayment(
                        client,
                        stats_repo,
                        account_id,
                        repayment.parent_operation_id,
                        repayment,
                    )
        except Exception as e:
            logger.error(f"Unexpected error in maturity stream: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)
