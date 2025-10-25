import logging
from datetime import datetime, timezone

from tinkoff.invest import (
    OrderBook,
    OrderDirection,
    OrderType,
    PortfolioPosition,
)
from tinkoff.invest.async_services import AsyncServices

from src.config import settings
from src.market.utils import normalize_quotation

from .schemas import NBond

logger = logging.getLogger(__name__)


async def get_account_id(client: AsyncServices) -> str:
    """
    Fetches account id.
    """
    response = await client.users.get_accounts()
    if not response.accounts:
        logger.error("There is no accounts")

    return response.accounts[0].id


async def get_existing_bonds(
    client: AsyncServices, account_id: str
) -> dict[str, PortfolioPosition]:
    """
    Fetches existing on account bonds.
    """
    positions = (
        await client.operations.get_portfolio(account_id=account_id)
    ).positions
    return {p.ticker: p for p in positions if p.instrument_type == "bond"}


async def get_account_balance(client: AsyncServices, account_id: str) -> float:
    """
    Fetches account balance.
    """
    return normalize_quotation(
        (await client.operations.get_positions(account_id=account_id)).money[0]
    )


async def buy_bond(client: AsyncServices, account_id: str, bond: NBond, quantity: int):
    """
    Posts market order to given bond by given quantity.
    """
    response = await client.orders.post_order(
        account_id=account_id,
        figi=bond.figi,
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_MARKET,
    )
    return normalize_quotation(response.total_order_amount)


async def fetch_coupons_sum(client: AsyncServices, bond: NBond) -> float:
    from_ = datetime.now(tz=timezone.utc)
    to = bond.maturity_date

    if to < from_:
        logging.warning("Skipping coupons fetching - `to` can't be less then `from`")
        return 0.0

    coupon_resp = await client.instruments.get_bond_coupons(
        figi=bond.figi, from_=from_, to=to
    )
    return sum(normalize_quotation(c.pay_one_bond) for c in coupon_resp.events)


async def fetch_bonds(client: AsyncServices) -> list[NBond]:
    """
    Fetches all available bonds on exchange.
    """
    response = await client.instruments.bonds()
    return [
        NBond.from_bond(
            bond,
            fee_percent=settings.FEE_PERCENT,
            orderbook=OrderBook(figi=bond.figi, asks=[]),
        )
        for bond in response.instruments
    ]
