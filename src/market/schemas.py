from datetime import datetime, timezone
from functools import cached_property
from typing import Self

from pydantic import BaseModel
from tinkoff.invest import Bond, Client, OrderBook

from src.config import settings

from .utils import normalize_quotation


class MarketData(BaseModel):
    fee_percent: float = 0.0
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

    @classmethod  # type: ignore
    def from_bond(cls, bond: Bond) -> Self:
        """Factory method to create NBond from Tinkoff Bond."""
        return cls(
            figi=bond.figi,
            ticker=bond.ticker,
            nominal=normalize_quotation(bond.nominal),
            aci_value=normalize_quotation(bond.aci_value),
            maturity_date=bond.maturity_date,
            risk_level=bond.risk_level,
            is_unlimited=bond.perpetual_flag,
            currency=bond.currency,
            nominal_currency=bond.nominal.currency,
            for_qual_investor=bond.for_qual_investor_flag,
            trading_status=bond.trading_status,
        )

    @property
    def days_to_maturity(self) -> int:
        return (self.maturity_date - datetime.now(tz=timezone.utc)).days

    @cached_property
    def coupons_sum(self) -> float:
        now = datetime.now(tz=timezone.utc)
        with Client(settings.TINVEST_TOKEN) as client:
            coupon_resp = client.instruments.get_bond_coupons(
                figi=self.figi,
                from_=now,
                to=self.maturity_date,
            )
            return sum(normalize_quotation(c.pay_one_bond) for c in coupon_resp.events)

    def update_market_data(self, orderbook: OrderBook, fee_percent: float) -> None:
        market_data = MarketData()
        market_data.fee_percent = fee_percent

        # normalize price from % to absolute value
        ask_price_percent = normalize_quotation(orderbook.asks[0].price)
        market_data.ask_quantity = orderbook.asks[0].quantity
        market_data.current_price = (self.nominal * ask_price_percent) / 100

        # calculate fee and real price including accrued coupon interest and fee
        market_data.fee = market_data.current_price * (market_data.fee_percent / 100)
        market_data.real_price = (
            market_data.current_price + self.aci_value + market_data.fee
        )

        # calculate total expected return (nominal + coupons)
        market_data.full_return = self.nominal + self.coupons_sum

        market_data.benefit = market_data.full_return - market_data.real_price

        # annualized yield as percentage
        market_data.annual_yield = (
            (market_data.benefit / market_data.real_price)
            * (365.25 / max(self.days_to_maturity, 1))
            * 100
        )

        self.market_data = market_data
