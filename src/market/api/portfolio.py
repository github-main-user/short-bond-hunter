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
    available: float | None
    reserved: float | None


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

    available = {money.currency: to_float(money) for money in positions.money}
    reserved = {money.currency: to_float(money) for money in positions.blocked}

    return AccountBalance(available=available.get("rub"), reserved=reserved.get("rub"))
