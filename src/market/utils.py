from __future__ import annotations

from typing import TYPE_CHECKING

from tinkoff.invest import MoneyValue, Quotation
from tinkoff.invest.schemas import RiskLevel

if TYPE_CHECKING:
    from src.market.schemas import NBond


def normalize_quotation(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)


def filter_bonds(bonds: list[NBond], maximum_days: int) -> list[NBond]:
    return [
        bond
        for bond in bonds
        if (
            not bond.for_qual_investor
            and not bond.is_unlimited
            and bond.currency == "rub"
            and bond.nominal_currency == "rub"
            and bond.days_to_maturity <= maximum_days
            and (
                RiskLevel.RISK_LEVEL_UNSPECIFIED
                < bond.risk_level
                < RiskLevel.RISK_LEVEL_HIGH
            )
        )
    ]