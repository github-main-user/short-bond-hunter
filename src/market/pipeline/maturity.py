import logging

from aiohttp import ClientError
from t_tech.invest.async_services import AsyncServices

from market.messages import compose_coupon_notification, compose_repayment_notification
from src.market.api import fetch_bond_by_figi, fetch_tmon_etf_price_at
from src.market.domain import MaturityEvent, MaturityEventType
from src.stats import MaturityRepository
from src.telegram import TelegramNotConfiguredError, send_telegram_message

logger = logging.getLogger(__name__)


async def _process_repayment(
    client: AsyncServices, repo: MaturityRepository, event: MaturityEvent
):
    if repo.is_repayment_exists(event.bond_figi):
        return

    bond = await fetch_bond_by_figi(client, event.bond_figi)

    if not bond:
        return

    tmon_price_at_maturity = await fetch_tmon_etf_price_at(client, bond.maturity_date)
    tmon_price_at_money_received = await fetch_tmon_etf_price_at(
        client, event.operation_date
    )

    if repo.is_coupon_exists(event.bond_figi):
        repo.update_repayment(
            bond_figi=event.bond_figi, principal_received=event.payment
        )
    else:
        repo.create_repayment(
            bond_name=bond.name,
            bond_figi=event.bond_figi,
            bond_ticker=bond.ticker,
            tmon_price_at_maturity=tmon_price_at_maturity,
            tmon_price_at_money_received=tmon_price_at_money_received,
            principal_received=event.payment,
            matured_at=bond.maturity_date,
            money_received_at=event.operation_date,
        )

    message = compose_repayment_notification(
        bond.ticker, bond.name, event.payment, event.is_missed
    )
    logger.info(message)
    try:
        await send_telegram_message(message)
    except (TelegramNotConfiguredError, ClientError) as e:
        logger.error(f"Failed to send telegram message: {e}")


async def _process_coupon(
    client: AsyncServices, repo: MaturityRepository, event: MaturityEvent
):
    if repo.is_coupon_exists(event.bond_figi):
        return

    bond = await fetch_bond_by_figi(client, event.bond_figi)

    if not bond:
        return

    if repo.is_repayment_exists(event.bond_figi):
        repo.update_coupon(bond_figi=event.bond_figi, coupon_received=event.payment)
    else:
        repo.create_coupon(
            bond_name=bond.name,
            bond_figi=event.bond_figi,
            bond_ticker=bond.ticker,
            coupon_received=event.payment,
            matured_at=bond.maturity_date,
            money_received_at=event.operation_date,
        )

    message = compose_coupon_notification(
        bond.ticker, bond.name, event.payment, event.is_missed
    )
    logger.info(message)
    try:
        await send_telegram_message(message)
    except (TelegramNotConfiguredError, ClientError) as e:
        logger.error(f"Failed to send telegram message: {e}")


_EVENT_TYPE_TO_FUNC = {
    MaturityEventType.REPAYMENT: _process_repayment,
    MaturityEventType.COUPON: _process_coupon,
}


async def process_maturity(
    client: AsyncServices, repo: MaturityRepository, event: MaturityEvent
):
    await _EVENT_TYPE_TO_FUNC[event.event_type](client, repo, event)
