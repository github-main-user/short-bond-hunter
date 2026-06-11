from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Self

from t_tech.invest import Bond, OrderBook

from .utils import normalize_quotation


class MaturityEventType(StrEnum):
    REPAYMENT = "REPAYMENT"
    COUPON = "COUPON"


@dataclass
class MaturityEvent:
    event_type: MaturityEventType
    bond_figi: str
    payment: float
    operation_date: datetime


@dataclass(frozen=True)
class PriceView:
    price_percent: float
    current_price: float
    commission: float
    real_price: float
    benefit: float
    annual_yield: float


@dataclass
class EnrichedBond:
    name: str
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
    commission_percent: float
    coupons_sum: float
    min_price_increment: float
    orderbook: OrderBook

    @property
    def days_to_maturity(self) -> int:
        return (self.maturity_date.date() - datetime.now(tz=timezone.utc).date()).days

    @property
    def full_return(self) -> float:
        return self.nominal + self.coupons_sum

    def at(self, price_percent: float) -> PriceView:
        current_price = (self.nominal * price_percent) / 100
        commission = current_price * (self.commission_percent / 100)
        real_price = current_price + self.aci_value + commission
        benefit = self.full_return - real_price

        days = self.days_to_maturity
        if days <= 0 or real_price <= 0:
            annual_yield = 0.0
        else:
            annual_yield = (benefit / real_price) * (365.25 / days) * 100

        return PriceView(
            price_percent=price_percent,
            current_price=current_price,
            commission=commission,
            real_price=real_price,
            benefit=benefit,
            annual_yield=annual_yield,
        )

    @property
    def ask_price_percent(self) -> float:
        return (
            normalize_quotation(self.orderbook.asks[0].price)
            if self.orderbook.asks
            else 0
        )

    @property
    def ask_quantity(self) -> int:
        return self.orderbook.asks[0].quantity if self.orderbook.asks else 0

    @property
    def bid_price_percent(self) -> float:
        return (
            normalize_quotation(self.orderbook.bids[0].price)
            if self.orderbook.bids
            else 0
        )

    @property
    def bid_quantity(self) -> int:
        return self.orderbook.bids[0].quantity if self.orderbook.bids else 0

    @property
    def ask(self) -> PriceView:
        return self.at(self.ask_price_percent)

    @property
    def bid(self) -> PriceView:
        return self.at(self.bid_price_percent)

    @classmethod
    def from_bond(
        cls,
        bond: Bond,
        commission_percent: float,
        coupons_sum: float,
        orderbook: OrderBook,
    ) -> Self:
        return cls(
            name=bond.name,
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
            commission_percent=commission_percent,
            coupons_sum=coupons_sum,
            min_price_increment=normalize_quotation(bond.min_price_increment),
            orderbook=orderbook,
        )

    def update(self, orderbook: OrderBook) -> None:
        self.orderbook = orderbook
