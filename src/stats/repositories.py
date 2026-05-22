import logging
from datetime import datetime

from .database import SessionLocal
from .models import BondMaturity, BondPurchase, RiskLevel

logger = logging.getLogger(__name__)


class PurchaseRepository:
    def create(
        self,
        bond_name: str,
        bond_figi: str,
        bond_ticker: str,
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
                    bond_name=bond_name,
                    bond_figi=bond_figi,
                    bond_ticker=bond_ticker,
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

    def get_all(self) -> list[BondPurchase]:
        with SessionLocal() as session:
            return session.query(BondPurchase).all()


class MaturityRepository:
    def has_principal_payment(self, figi: str) -> bool:
        with SessionLocal() as session:
            record = session.query(BondMaturity).filter_by(bond_figi=figi).first()
            return record is not None and record.principal_received is not None

    def has_coupon_payment(self, figi: str) -> bool:
        with SessionLocal() as session:
            record = session.query(BondMaturity).filter_by(bond_figi=figi).first()
            return record is not None and record.coupon_received is not None

    def create_repayment(
        self,
        bond_name: str,
        bond_figi: str,
        bond_ticker: str,
        tmon_price_at_maturity: float | None,
        tmon_price_at_money_received: float | None,
        principal_received: float,
        matured_at: datetime,
        money_received_at: datetime,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                BondMaturity(
                    bond_name=bond_name,
                    bond_figi=bond_figi,
                    bond_ticker=bond_ticker,
                    tmon_price_at_maturity=tmon_price_at_maturity,
                    tmon_price_at_money_received=tmon_price_at_money_received,
                    principal_received=principal_received,
                    matured_at=matured_at,
                    money_received_at=money_received_at,
                )
            )
            session.commit()

    def create_coupon(
        self,
        bond_name: str,
        bond_figi: str,
        bond_ticker: str,
        coupon_received: float,
        matured_at: datetime,
        money_received_at: datetime,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                BondMaturity(
                    bond_name=bond_name,
                    bond_figi=bond_figi,
                    bond_ticker=bond_ticker,
                    coupon_received=coupon_received,
                    matured_at=matured_at,
                    money_received_at=money_received_at,
                )
            )
            session.commit()

    def update_repayment(
        self,
        bond_figi: str,
        principal_received: float,
        tmon_price_at_maturity: float | None,
        tmon_price_at_money_received: float | None,
    ) -> None:
        with SessionLocal() as session:
            record = session.query(BondMaturity).filter_by(bond_figi=bond_figi).first()
            if record:
                record.principal_received = principal_received
                record.tmon_price_at_maturity = tmon_price_at_maturity
                record.tmon_price_at_money_received = tmon_price_at_money_received
                session.commit()

    def update_coupon(
        self,
        bond_figi: str,
        coupon_received: float | None = None,
    ) -> None:
        with SessionLocal() as session:
            record = session.query(BondMaturity).filter_by(bond_figi=bond_figi).first()
            if record:
                if coupon_received is not None:
                    record.coupon_received = coupon_received
                session.commit()

    def get_all(self) -> list[BondMaturity]:
        with SessionLocal() as session:
            return session.query(BondMaturity).all()
