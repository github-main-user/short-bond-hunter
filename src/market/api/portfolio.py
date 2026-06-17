import logging

from t_tech.invest import PortfolioPosition
from t_tech.invest.async_services import AsyncServices

from src.market.utils import to_float

logger = logging.getLogger(__name__)


async def fetch_bond_positions(
    client: AsyncServices, account_id: str
) -> dict[str, PortfolioPosition]:
    positions = (await client.operations.get_portfolio(account_id=account_id)).positions
    return {p.figi: p for p in positions if p.instrument_type == "bond"}


async def fetch_account_balance_rub(
    client: AsyncServices, account_id: str
) -> float | None:
    money = (await client.operations.get_positions(account_id=account_id)).money
    money_rub = next((m for m in money if m.currency == "rub"), None)
    if money_rub is None:
        logger.warning(
            f"No money positions with currency RUB found for account {account_id}"
        )
        return
    return to_float(money_rub)
