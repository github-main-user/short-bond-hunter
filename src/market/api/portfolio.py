import structlog
from t_tech.invest.grpc.schemas import (
    PortfolioPosition,
    PortfolioRequest,
    PositionsRequest,
)
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.market.utils import to_float

log = structlog.get_logger(__name__)


async def fetch_bond_positions(
    client: AsyncServices, account_id: str
) -> dict[str, PortfolioPosition]:
    positions = (
        await client.operations.get_portfolio(
            request=PortfolioRequest(account_id=account_id)
        )
    ).positions
    return {p.figi: p for p in positions if p.instrument_type == "bond"}


async def fetch_account_balance_rub(
    client: AsyncServices, account_id: str
) -> float | None:
    money = (
        await client.operations.get_positions(
            request=PositionsRequest(account_id=account_id)
        )
    ).money
    money_rub = next((m for m in money if m.currency == "rub"), None)
    if money_rub is None:
        log.warning("no_rub_balance", account_id=account_id)
        return None
    return to_float(money_rub)
