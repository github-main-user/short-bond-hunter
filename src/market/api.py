import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from t_tech.invest import (
    Bond,
    Operation,
    OperationState,
    OperationType,
    OrderDirection,
    OrderType,
    PortfolioPosition,
)
from t_tech.invest.async_services import AsyncServices

from src.market.utils import normalize_quotation

if TYPE_CHECKING:
    from src.market.schemas import NBond

logger = logging.getLogger(__name__)


async def fetch_account_id(client: AsyncServices) -> str:
    response = await client.users.get_accounts()
    if not response.accounts:
        logger.error("No accounts found")

    return response.accounts[0].id


async def fetch_user_commission(client: AsyncServices) -> float:
    _TBANK_TARIFF_COMMISSION = {
        "investor": 0.3,
        "trader": 0.05,
        "premium": 0.04,
    }

    response = await client.users.get_info()

    tariff_percent = _TBANK_TARIFF_COMMISSION[response.tariff]
    logger.info(f"User's tariff: {response.tariff} ({tariff_percent}%)")

    return tariff_percent


async def fetch_existing_bonds(
    client: AsyncServices, account_id: str
) -> dict[str, PortfolioPosition]:
    positions = (await client.operations.get_portfolio(account_id=account_id)).positions
    return {p.ticker: p for p in positions if p.instrument_type == "bond"}


async def fetch_account_balance(client: AsyncServices, account_id: str) -> float:
    money = (await client.operations.get_positions(account_id=account_id)).money
    if not money:
        logger.error(f"No money positions found for account {account_id}")
        return 0.0
    return normalize_quotation(money[0])


async def buy_bond(
    client: AsyncServices, account_id: str, bond: "NBond", quantity: int
):

    response = await client.orders.post_order(
        account_id=account_id,
        figi=bond.figi,
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_MARKET,
    )
    return normalize_quotation(response.total_order_amount)


async def fetch_coupons_sum(
    client: AsyncServices, figi: str, maturity_date: datetime
) -> float:
    from_ = datetime.now(tz=timezone.utc)
    to = maturity_date

    if to < from_:
        logger.warning("Skipping coupons fetch - `to` can't be less than `from`")
        return 0.0

    coupon_resp = await client.instruments.get_bond_coupons(
        figi=figi, from_=from_, to=to
    )
    return sum(normalize_quotation(c.pay_one_bond) for c in coupon_resp.events)


async def fetch_raw_bonds(client: AsyncServices) -> list[Bond]:
    response = await client.instruments.bonds()
    return response.instruments


async def fetch_tmon_etf_price(client: AsyncServices) -> float | None:
    orderbook = await client.market_data.get_order_book(figi="TCS70A106DL2", depth=1)
    if not orderbook.asks:
        logger.warning("Can't fetch TMON@ price: no orderbook available")
        return
    return normalize_quotation(orderbook.asks[0].price)


async def fetch_maturity_operations(
    client: AsyncServices, account_id: str, since: datetime
) -> list[Operation]:
    response = await client.operations.get_operations(
        account_id=account_id,
        from_=since,
        to=datetime.now(tz=timezone.utc),
        state=OperationState.OPERATION_STATE_EXECUTED,
    )
    return [
        op
        for op in response.operations
        if op.operation_type
        in (
            OperationType.OPERATION_TYPE_BOND_REPAYMENT_FULL,
            OperationType.OPERATION_TYPE_COUPON,
        )
    ]


async def fetch_coupon_for_repayment(
    client: AsyncServices,
    account_id: str,
    instrument_uid: str,
    repayment_date: datetime,
) -> Operation | None:
    response = await client.operations.get_operations(
        account_id=account_id,
        from_=repayment_date - timedelta(hours=2),  # type: ignore
        to=repayment_date + timedelta(minutes=15),
        state=OperationState.OPERATION_STATE_EXECUTED,
    )
    for op in response.operations:
        if (
            op.operation_type == OperationType.OPERATION_TYPE_COUPON
            and op.instrument_uid == instrument_uid
        ):
            return op
    return None
