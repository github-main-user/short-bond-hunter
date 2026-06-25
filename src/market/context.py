from dataclasses import dataclass

from t_tech.invest.grpc.utils.grpc_services import AsyncServices

from src.market.bid_order_registry import BidOrderRegistry
from src.market.bond_catalog import BondCatalog
from src.market.cooldown_registry import CooldownRegistry
from src.stats import MaturityRepository, PurchaseRepository


@dataclass
class MarketContext:
    client: AsyncServices
    account_id: str
    bid_registry: BidOrderRegistry
    catalog: BondCatalog
    cooldown_registry: CooldownRegistry
    purchase_repo: PurchaseRepository
    maturity_repo: MaturityRepository
