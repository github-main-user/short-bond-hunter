import asyncio
import logging

from t_tech.invest import OrderBook
from t_tech.invest.async_services import AsyncServices

from src.config import settings
from src.market.api import fetch_coupons_sum, fetch_raw_bonds, fetch_user_commission
from src.market.domain import EnrichedBond
from src.market.utils import filter_bonds

logger = logging.getLogger(__name__)
