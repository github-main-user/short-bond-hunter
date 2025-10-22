import logging

from tinkoff.invest import (
    Client,
    OrderDirection,
    OrderType,
    PortfolioPosition,
)

from src.config import settings
from src.market.utils import normalize_quotation

from .schemas import NBond

logger = logging.getLogger(__name__)


def get_existing_bonds(account_id: str) -> dict[str, PortfolioPosition]:
    with Client(settings.TINVEST_TOKEN) as client:
        positions = client.operations.get_portfolio(account_id=account_id).positions
        return {p.ticker: p for p in positions if p.instrument_type == "bond"}


def get_account_id() -> str:
    with Client(settings.TINVEST_TOKEN) as client:
        response = client.users.get_accounts()
        if not response.accounts:
            logger.error("There is no accounts")

        return response.accounts[0].id


def get_account_balance(account_id: str) -> float:
    with Client(settings.TINVEST_TOKEN) as client:
        return normalize_quotation(
            client.operations.get_positions(account_id=account_id).money[0]
        )


def buy_bond(account_id: str, bond: NBond, quantity: int):
    with Client(settings.TINVEST_TOKEN) as client:
        response = client.orders.post_order(
            account_id=account_id,
            figi=bond.figi,
            quantity=quantity,
            direction=OrderDirection.ORDER_DIRECTION_BUY,
            order_type=OrderType.ORDER_TYPE_MARKET,
        )
        return normalize_quotation(response.total_order_amount)


def fetch_bonds() -> list[NBond]:
    with Client(settings.TINVEST_TOKEN) as client:
        response = client.instruments.bonds()
        return [
            NBond.from_bond(bond, settings.FEE_PERCENT) for bond in response.instruments
        ]
