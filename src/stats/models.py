from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class RiskLevel(StrEnum):
    UNSPECIFIED = "UNSPECIFIED"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

    @classmethod
    def from_int(cls, value: int) -> "RiskLevel":
        return [cls.UNSPECIFIED, cls.LOW, cls.MODERATE, cls.HIGH][value]


class PurchaseStrategy(StrEnum):
    ASK_SNIPER = "ASK_SNIPER"
    BID_WAITER = "BID_WAITER"


class Base(DeclarativeBase):
    pass


class BondPurchase(Base):
    __tablename__ = "bond_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_name: Mapped[str]
    bond_figi: Mapped[str]
    bond_ticker: Mapped[str]
    quantity: Mapped[int]
    nominal: Mapped[float]
    price: Mapped[float]
    aci_value: Mapped[float]
    commission_percent: Mapped[float]
    real_price: Mapped[float]
    coupons_sum: Mapped[float]
    risk_level: Mapped[RiskLevel] = mapped_column(String())
    tmon_price_at_buy: Mapped[float | None]
    expected_maturity_date: Mapped[datetime]
    strategy: Mapped[PurchaseStrategy] = mapped_column(String())
    bought_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(tz=timezone.utc)
    )


class BondMaturity(Base):
    __tablename__ = "bond_maturities"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_name: Mapped[str]
    bond_figi: Mapped[str] = mapped_column(unique=True)
    bond_ticker: Mapped[str]
    tmon_price_at_maturity: Mapped[float | None]
    tmon_price_at_money_received: Mapped[float | None]
    principal_received: Mapped[float | None]
    coupon_received: Mapped[float | None]
    matured_at: Mapped[datetime]
    money_received_at: Mapped[datetime]

    @property
    def money_received(self) -> float:
        return (self.principal_received or 0) + (self.coupon_received or 0)
