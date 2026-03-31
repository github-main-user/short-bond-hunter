import logging
from datetime import datetime

from src.stats.database import SessionLocal
from src.stats.models import BondMaturity, BondPurchase, RiskLevel

logger = logging.getLogger(__name__)


class StatsRepository:
    def save_purchase(
        self,
        figi: str,
        ticker: str,
        quantity: int,
        nominal: float,
        price: float,
        aci_value: float,
        commission_percent: float,
        real_price: float,
        coupons_sum: float,
        risk_level: int,
        tmon_price: float | None,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                BondPurchase(
                    bond_figi=figi,
                    bond_ticker=ticker,
                    quantity=quantity,
                    nominal=nominal,
                    price=price,
                    aci_value=aci_value,
                    commission_percent=commission_percent,
                    real_price=real_price,
                    coupons_sum=coupons_sum,
                    risk_level=RiskLevel.from_int(risk_level),
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
        principal_received: float,
        coupon_received: float | None,
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
                    principal_received=principal_received,
                    coupon_received=coupon_received,
                    matured_at=matured_at,
                    money_received_at=money_received_at,
                )
            )
            session.commit()
