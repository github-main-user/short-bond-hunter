from dataclasses import dataclass

from t_tech.invest.grpc.schemas import (
    PortfolioPosition,
    PortfolioRequest,
    PositionsRequest,
)
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.market.utils import to_float


@dataclass(frozen=True)
class AccountBalance:
    available: float
    reserved: float


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
) -> AccountBalance:
    positions = await client.operations.get_positions(
        request=PositionsRequest(account_id=account_id)
    )

    money_rub = next((m for m in positions.money if m.currency == "rub"), None)
    blocked_rub = next((m for m in positions.blocked if m.currency == "rub"), None)

    return AccountBalance(
        available=to_float(money_rub) if money_rub is not None else 0.0,
        reserved=to_float(blocked_rub) if blocked_rub is not None else 0.0,
    )
