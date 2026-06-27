import structlog
from t_tech.invest.grpc.utils.grpc_services import AsyncServices

log = structlog.get_logger(__name__)

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
    log.info(
        "user_tariff_fetched",
        tariff_name=response.tariff,
        tariff_percent=tariff_percent,
    )

    return tariff_percent
