from datetime import datetime
from typing import Self

from pydantic import BaseModel
from tinkoff.invest import Bond

from . import utils


class MarketData(BaseModel):
    fee_percent: float = 0.0
    coupons_sum: float = 0.0
    current_price: float = 0.0
    fee: float = 0.0
    real_price: float = 0.0
    full_return: float = 0.0
    benefit: float = 0.0
    annual_yield: float = 0.0
    ask_quantity: int = 0


class NBond(BaseModel):
    figi: str
    ticker: str
    nominal: float
    aci_value: float
    maturity_date: datetime
    risk_level: int
    is_unlimited: bool
    currency: str
    nominal_currency: str
    for_qual_investor: bool
    trading_status: int
    market_data: MarketData | None = None

    @classmethod
    def from_bond(cls, bond: Bond) -> Self:
        """Factory method to create NBond from Tinkoff Bond."""
        return cls(
            figi=bond.figi,
            ticker=bond.ticker,
            nominal=utils.normalize_quotation(bond.nominal),
            aci_value=utils.normalize_quotation(bond.aci_value),
            maturity_date=bond.maturity_date,
            risk_level=bond.risk_level,
            is_unlimited=bond.perpetual_flag,
            currency=bond.currency,
            nominal_currency=bond.nominal.currency,
            for_qual_investor=bond.for_qual_investor_flag,
            trading_status=bond.trading_status,
        )
