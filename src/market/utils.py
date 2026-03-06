from __future__ import annotations

from datetime import datetime, timezone

from t_tech.invest import Bond, MoneyValue, Quotation
from t_tech.invest.schemas import RiskLevel


def normalize_quotation(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)


def filter_bonds(bonds: list[Bond], maximum_days: int) -> list[Bond]:
    now = datetime.now(tz=timezone.utc).date()
    return [
        bond
        for bond in bonds
        if (
            not bond.for_qual_investor_flag
            and not bond.perpetual_flag
            and bond.currency == "rub"
            and bond.nominal.currency == "rub"
            and (bond.maturity_date.date() - now).days <= maximum_days
            and (
                RiskLevel.RISK_LEVEL_UNSPECIFIED
                < bond.risk_level
                < RiskLevel.RISK_LEVEL_HIGH
            )
        )
    ]
