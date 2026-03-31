from datetime import datetime
from enum import Enum

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class RiskLevel(Enum):
    UNSPECIFIED = "UNSPECIFIED"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

    @classmethod  # type: ignore
    def from_int(cls, value: int) -> "RiskLevel":
        return [cls.UNSPECIFIED, cls.LOW, cls.MODERATE, cls.HIGH][value]


class Base(DeclarativeBase):
    pass


class BondPurchase(Base):
    __tablename__ = "bond_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_figi: Mapped[str]
    bond_ticker: Mapped[str]
    quantity: Mapped[int]
    nominal: Mapped[float]
    price: Mapped[float]
    aci_value: Mapped[float]
    commission_percent: Mapped[float]
    real_price: Mapped[float]
    coupons_sum: Mapped[float]
    risk_level: Mapped[RiskLevel]
    tmon_price_at_buy: Mapped[float | None]
    bought_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BondMaturity(Base):
    __tablename__ = "bond_maturities"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[str] = mapped_column(unique=True)
    bond_figi: Mapped[str]
    bond_ticker: Mapped[str]
    tmon_price_at_maturity: Mapped[float | None]
    tmon_price_at_money_received: Mapped[float | None]
    principal_received: Mapped[float]
    coupon_received: Mapped[float | None]
    matured_at: Mapped[datetime]
    money_received_at: Mapped[datetime]
