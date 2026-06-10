from dataclasses import dataclass

from t_tech.invest.async_services import AsyncServices

from src.market.order_registry import OrderRegistry
from src.stats import PurchaseRepository


@dataclass
class MarketContext:
    client: AsyncServices
    account_id: str
    registry: OrderRegistry
    purchase_repo: PurchaseRepository
