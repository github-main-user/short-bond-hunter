import logging
from datetime import datetime, timezone
from functools import lru_cache

from tinkoff.invest import (
    OrderBook,
    OrderDirection,
    OrderType,
    PortfolioPosition,
)
from tinkoff.invest.services import Services

from src.config import settings
from src.market.utils import normalize_quotation

from .schemas import NBond

logger = logging.getLogger(__name__)


@lru_cache
def get_account_id(client: Services) -> str:
    """
    Fetches account id.
    Caches the result using LRU cache.
    """
    response = client.users.get_accounts()
    if not response.accounts:
        logger.error("There is no accounts")

    return response.accounts[0].id


def get_existing_bonds(
    client: Services, account_id: str
) -> dict[str, PortfolioPosition]:
    """
    Fetches existing on account bonds.
    """
    positions = client.operations.get_portfolio(account_id=account_id).positions
    return {p.ticker: p for p in positions if p.instrument_type == "bond"}


def get_account_balance(client: Services, account_id: str) -> float:
    """
    Fetches account balance.
    """
    return normalize_quotation(
        client.operations.get_positions(account_id=account_id).money[0]
    )


def buy_bond(client: Services, account_id: str, bond: NBond, quantity: int):
    """
    Posts market order to given bond by given quantity.
    """
    response = client.orders.post_order(
        account_id=account_id,
        figi=bond.figi,
        quantity=quantity,
        direction=OrderDirection.ORDER_DIRECTION_BUY,
        order_type=OrderType.ORDER_TYPE_MARKET,
    )
    return normalize_quotation(response.total_order_amount)


def fetch_coupons_sum(client: Services, bond: NBond) -> float:
    from_ = datetime.now(tz=timezone.utc)
    to = bond.maturity_date

    if to < from_:
        logging.warning("Skipping coupons fetching - `to` can't be less then `from`")
        return 0.0

    coupon_resp = client.instruments.get_bond_coupons(
        figi=bond.figi, from_=from_, to=to
    )
    return sum(normalize_quotation(c.pay_one_bond) for c in coupon_resp.events)


def fetch_bonds(client: Services) -> list[NBond]:
    """
    Fetches all available bonds on exchange.
    """
    response = client.instruments.bonds()
    return [
        NBond.from_bond(
            bond,
            fee_percent=settings.FEE_PERCENT,
            orderbook=OrderBook(figi=bond.figi, asks=[]),
        )
        for bond in response.instruments
    ]
