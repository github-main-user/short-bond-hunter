import logging
from datetime import datetime

from src.market import NBond
from src.stats.database import SessionLocal
from src.stats.models import BondMaturity, BondPurchase

logger = logging.getLogger(__name__)


class StatsRepository:
    def save_purchase(
        self,
        bond: NBond,
        quantity: int,
        money_spent_per_unit: float,
        tmon_price: float | None,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                BondPurchase(
                    bond_figi=bond.figi,
                    bond_ticker=bond.ticker,
                    quantity=quantity,
                    money_spent_per_unit=money_spent_per_unit,
                    tmon_price_at_buy=tmon_price,
                )
            )
            session.commit()

    def is_maturity_recorded(self, operation_id: str) -> bool:
        with SessionLocal() as session:
            return session.query(
                session.query(BondMaturity)
                .filter_by(operation_id=operation_id)
                .exists()
            ).scalar()

    def save_maturity(
        self,
        operation_id: str,
        figi: str,
        ticker: str,
        tmon_price_at_maturity: float | None,
        tmon_price_at_money_received: float | None,
        money_received: float,
        matured_at: datetime,
        money_received_at: datetime,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                BondMaturity(
                    operation_id=operation_id,
                    bond_figi=figi,
                    bond_ticker=ticker,
                    tmon_price_at_maturity=tmon_price_at_maturity,
                    tmon_price_at_money_received=tmon_price_at_money_received,
                    money_received=money_received,
                    matured_at=matured_at,
                    money_received_at=money_received_at,
                )
            )
            session.commit()
