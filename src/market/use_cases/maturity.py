import logging

from src.market.api import fetch_bond_by_figi, fetch_tmon_etf_price_at
from src.market.context import MarketContext
from src.market.domain import MaturityEvent, MaturityEventType
from src.market.messages import (
    compose_coupon_notification,
    compose_repayment_notification,
)
from src.telegram import notify

logger = logging.getLogger(__name__)


async def _process_repayment(ctx: MarketContext, event: MaturityEvent):
    repo = ctx.maturity_repo
    if repo.has_principal_payment(event.bond_figi):
        return

    bond = await fetch_bond_by_figi(ctx.client, event.bond_figi)

    if not bond:
        return

    tmon_price_at_maturity = await fetch_tmon_etf_price_at(
        ctx.client, bond.maturity_date
    )
    tmon_price_at_money_received = await fetch_tmon_etf_price_at(
        ctx.client, event.operation_date
    )

    if repo.has_coupon_payment(event.bond_figi):
        repo.update_repayment(
            bond_figi=event.bond_figi,
            principal_received=event.payment,
            tmon_price_at_maturity=tmon_price_at_maturity,
            tmon_price_at_money_received=tmon_price_at_money_received,
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

    message = compose_repayment_notification(bond.ticker, bond.name, event.payment)
    await notify(message)


async def _process_coupon(ctx: MarketContext, event: MaturityEvent):
    repo = ctx.maturity_repo
    if repo.has_coupon_payment(event.bond_figi):
        return

    bond = await fetch_bond_by_figi(ctx.client, event.bond_figi)

    if not bond:
        return

    if repo.has_principal_payment(event.bond_figi):
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

    message = compose_coupon_notification(bond.ticker, bond.name, event.payment)
    await notify(message)


_EVENT_TYPE_TO_FUNC = {
    MaturityEventType.REPAYMENT: _process_repayment,
    MaturityEventType.COUPON: _process_coupon,
}


async def process_maturity(ctx: MarketContext, event: MaturityEvent):
    logger.info(
        f'Processing maturity event of type "{event.event_type.value}"'
        f' for figi "{event.bond_figi}"'
    )
    await _EVENT_TYPE_TO_FUNC[event.event_type](ctx, event)
