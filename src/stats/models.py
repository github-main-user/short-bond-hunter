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
    tmon_price_at_buy: Mapped[float]
    bought_at: Mapped[datetime] = mapped_column(server_default=func.now())
