import asyncio
import logging

from t_tech.invest import (
    AsyncClient,
    MarketDataRequest,
    OperationType,
    OrderBookInstrument,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from t_tech.invest.async_services import AsyncServices
from t_tech.invest.schemas import OperationsStreamRequest

from src.config import settings
from src.market.api import fetch_account_id
from src.market.maturity import _process_maturity_repayment, check_missed_maturities
from src.market.purchase import process_bond_for_purchase
from src.market.schemas import NBond
from src.market.services import get_tradable_bonds
from src.stats import StatsRepository

logger = logging.getLogger(__name__)


async def _handle_market_data_stream(
    client: AsyncServices, bonds: list[NBond], stats_repo: StatsRepository
) -> None:
    figi_to_bond_map = {b.figi: b for b in bonds}
    account_id = await fetch_account_id(client)

    async def request_iterator():
        yield MarketDataRequest(
            subscribe_order_book_request=SubscribeOrderBookRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[OrderBookInstrument(figi=b.figi, depth=1) for b in bonds],
            )
        )
        while True:
            await asyncio.sleep(1)

    logger.info(f"Subscribed to {len(bonds)} bonds")

    async def stream_processor():
        async for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if not marketdata.orderbook:
                logger.info("Skipped market data: no orderbook")
                continue

            bond = figi_to_bond_map.get(marketdata.orderbook.figi)
            if not bond:
                logger.debug(
                    f"Skipped update for bond {marketdata.orderbook.figi} "
                    "(figi): not in the list"
                )
                continue

            old_price = bond.real_price
            bond.orderbook = marketdata.orderbook

            # if price changed
            if old_price != bond.real_price:
                await process_bond_for_purchase(client, bond, stats_repo, account_id)

    processor_task = asyncio.create_task(stream_processor())

    try:
        await asyncio.wait_for(
            processor_task, timeout=settings.BOND_REFRESH_INTERVAL_SECONDS
        )
    except asyncio.TimeoutError:
        logger.info("Bonds update interval reached. Re-fetching...")
    finally:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            logger.debug("Market data stream processing task cancelled.")


async def _maturity_stream_iteration(
    account_id: str, stats_repo: StatsRepository
) -> None:
    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        logger.info("Subscribing to operations stream")
        request = OperationsStreamRequest(accounts=[account_id])
        async for response in client.operations_stream.operations_stream(request):
            if not response.operation:
                continue
            repayment = response.operation
            if repayment.type != OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL:
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


async def _with_retry(fn, label: str) -> None:
    while True:
        try:
            await fn()
        except Exception as e:
            logger.error(f"Unexpected error in {label}: {e}")
            logger.info("Retrying in 5 minutes...")
            await asyncio.sleep(60 * 5)


async def _market_data_iteration(stats_repo: StatsRepository) -> None:
    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        bonds = await get_tradable_bonds(client)
        await _handle_market_data_stream(client, bonds, stats_repo)


async def start_market_streaming_session() -> None:
    stats_repo = StatsRepository()

    async with AsyncClient(settings.TINVEST_TOKEN) as client:
        account_id = await fetch_account_id(client)
        await check_missed_maturities(client, account_id, stats_repo)

    await asyncio.gather(
        _with_retry(lambda: _market_data_iteration(stats_repo), "market data stream"),
        _with_retry(
            lambda: _maturity_stream_iteration(account_id, stats_repo),
            "maturity stream",
        ),
    )
