import logging

from t_tech.invest.grpc.utils.grpc_services import AsyncServices

logger = logging.getLogger(__name__)

_TBANK_TARIFF_COMMISSION = {
    "investor": 0.3,
    "trader": 0.05,
    "premium": 0.04,
}


async def fetch_account_id(client: AsyncServices) -> str:
    response = await client.users.get_accounts()
    if not response.accounts:
        raise RuntimeError("No accounts found")

    return response.accounts[0].id


async def fetch_user_commission(client: AsyncServices) -> float:
    response = await client.users.get_info()

    tariff_percent = _TBANK_TARIFF_COMMISSION[response.tariff]
    logger.info(f"User's tariff: {response.tariff} ({tariff_percent}%)")

    return tariff_percent
