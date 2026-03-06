import logging

from src.market.schemas import NBond
from src.stats.database import SessionLocal
from src.stats.models import BondPurchase

logger = logging.getLogger(__name__)


class StatsRepository:
    def save_purchase(
        self, bond: NBond, quantity: int, money_spent_per_unit: float, tmon_price: float
    ) -> None:
        if tmon_price <= 0:
            logger.warning(
                "Skipping stats for %s: TMON price is unavailable", bond.ticker
            )
            return
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
