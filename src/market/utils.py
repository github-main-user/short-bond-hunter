from datetime import datetime, timedelta

from tinkoff.invest import MoneyValue, Quotation
from tinkoff.invest.schemas import RiskLevel

from src.market.schemas import NBond


def normalize_quotation(money: MoneyValue | Quotation) -> float:
    return money.units + (money.nano / 1e9)


def filter_bonds(bonds: list[NBond], maximum_days: int) -> list[NBond]:
    from_date = datetime.now()
    to_date = from_date + timedelta(days=maximum_days)

    return [
        bond
        for bond in bonds
        if (
            not bond.for_qual_investor
            and not bond.is_unlimited
            and bond.currency == "rub"
            and bond.nominal_currency == "rub"
            and from_date < bond.maturity_date
            and bond.maturity_date <= to_date
            and bond.risk_level < RiskLevel.RISK_LEVEL_HIGH
        )
    ]
