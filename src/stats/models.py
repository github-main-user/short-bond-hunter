from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BondPurchase(Base):
    __tablename__ = "bond_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    bond_figi: Mapped[str]
    bond_ticker: Mapped[str]
    quantity: Mapped[int]
    money_spent_per_unit: Mapped[float]
    tmon_price_at_buy: Mapped[float | None]
    bought_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BondMaturity(Base):
    __tablename__ = "bond_maturities"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[str] = mapped_column(unique=True)
    bond_figi: Mapped[str]
    bond_ticker: Mapped[str]
    tmon_price_at_maturity: Mapped[float | None]
    money_received: Mapped[float]
    matured_at: Mapped[datetime]
    money_received_at: Mapped[datetime]
