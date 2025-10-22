from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from typing import Self

from tinkoff.invest import Bond, Client, OrderBook

from src.config import settings

from .utils import normalize_quotation


@dataclass
class NBond:
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
    fee_percent: float
    _coupons_sum: float
    _orderbook: OrderBook

    @classmethod  # type: ignore
    def from_bond(cls, bond: Bond, fee_percent: float, orderbook: OrderBook) -> Self:
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
            fee_percent=fee_percent,
            _coupons_sum=0.0,
            _orderbook=orderbook,
        )

    @property
    def days_to_maturity(self) -> int:
        return (self.maturity_date.date() - datetime.now(tz=timezone.utc).date()).days

    @property
    def ask_quantity(self) -> int:
        return self.orderbook.asks[0].quantity if self.orderbook.asks else 0

    @property
    def ask_price_percent(self) -> float:
        return (
            normalize_quotation(self.orderbook.asks[0].price)
            if self.orderbook.asks
            else 0
        )

    @property
    def current_price(self) -> float:
        return (self.nominal * self.ask_price_percent) / 100

    @property
    def fee(self) -> float:
        return self.current_price * (self.fee_percent / 100)

    @property
    def real_price(self) -> float:
        return self.current_price + self.aci_value + self.fee

    @property
    def full_return(self) -> float:
        return self.nominal + self.coupons_sum

    @property
    def benefit(self) -> float:
        return self.full_return - self.real_price

    @property
    def annual_yield(self) -> float:
        days = self.days_to_maturity

        if days <= 0:
            return 0.0

        return (self.benefit / self.real_price) * (365.25 / days) * 100

    @property
    def orderbook(self) -> OrderBook:
        return self._orderbook

    @orderbook.setter
    def orderbook(self, orderbook: OrderBook) -> None:
        self._orderbook = orderbook

    @property
    def coupons_sum(self) -> float:
        return self._coupons_sum

    @coupons_sum.setter
    def coupons_sum(self, coupons_sum: float) -> None:
        self._coupons_sum = coupons_sum
