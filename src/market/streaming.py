import asyncio
import logging

from aiohttp.client_exceptions import ClientError
from tinkoff.invest import (
    AsyncClient,
    MarketDataRequest,
    OrderBookInstrument,
    RequestError,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)
from tinkoff.invest.async_services import AsyncServices

from src.config import settings
from src.market.schemas import NBond
from src.market.services import (
    buy_bond,
    fetch_bonds,
    fetch_coupons_sum,
    get_account_balance,
    get_account_id,
    get_existing_bonds,
)
from src.market.utils import filter_bonds, normalize_quotation
from src.telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def is_bond_eligible_for_purchase(bond: NBond) -> bool:
    """
    Checks if a bond is eligible for purchase based on predefined criteria.
    """
    if not (
        settings.ANNUAL_YIELD_MIN <= bond.annual_yield <= settings.ANNUAL_YIELD_MAX
    ):
        logger.info(
            "Ineligible bond %s: Annual yield (%s%%) is not in the allowed range (%s%%, %s%%)",
            bond.ticker,
            format(bond.annual_yield, ".2f"),
            settings.ANNUAL_YIELD_MIN,
            settings.ANNUAL_YIELD_MAX,
        )
        return False

    if bond.real_price <= 0:
        logger.info("Ineligible bond %s: `real_price` is not positive", bond.ticker)
        return False

    return True


async def calculate_purchase_quantity(
    client: AsyncServices, bond: NBond, account_id: str
) -> int:
    """
    Calculates the quantity of a bond to purchase.
    """
    balance = await get_account_balance(client, account_id)
    existing_bonds = await get_existing_bonds(client, account_id)
    existing_bond = existing_bonds.get(bond.ticker)

    quantity_to_buy_single = int(settings.BOND_SUM_MAX_SINGLE // bond.real_price)

    if existing_bond:
        current_value = normalize_quotation(
            existing_bond.quantity
        ) * normalize_quotation(existing_bond.current_price)
        allowed_budget = settings.BOND_SUM_MAX - current_value
    else:
        allowed_budget = settings.BOND_SUM_MAX

    quantity_allowed_to_buy = 0
    if allowed_budget > 0:
        quantity_allowed_to_buy = int(allowed_budget // bond.real_price)

    quantity_available_to_buy = int(balance // bond.real_price)

    return min(
        quantity_to_buy_single,
        quantity_allowed_to_buy,
        quantity_available_to_buy,
        bond.ask_quantity,
    )


def _format_purchase_notification(
    bond: NBond, buy_quantity: int, buy_price: float
) -> str:
    """
    Formats a notification message for a successful bond purchase.
    """
    return (
        f"Bought {buy_quantity} of `{bond.ticker}` ({bond.annual_yield:.2f}%)\n"
        f"Available: {bond.ask_quantity}\n"
        f"Expected price: {bond.real_price * buy_quantity:.2f}₽\n"
        f"Actual price: {buy_price:.2f}₽\n"
        f"Benefit per 1: {bond.benefit:.2f}₽ in {bond.days_to_maturity} days "
        f"({bond.benefit / bond.days_to_maturity:.2f}₽ per day)"
    )


async def process_bond_for_purchase(client: AsyncServices, bond: NBond) -> None:
    """
    Processes a bond for purchase, including eligibility checks, quantity calculation,
    and execution.
    """
    logger.info(
        "Processing bond: %s (%sd, %s%%) (%s₽ + %s₽ + %s₽ = %s₽)",
        bond.ticker,
        bond.days_to_maturity,
        format(bond.annual_yield, ".2f"),
        format(bond.current_price, ".2f"),
        format(bond.aci_value, ".2f"),
        format(bond.fee, ".2f"),
        format(bond.real_price, ".2f"),
    )

    if not is_bond_eligible_for_purchase(bond):
        return

    account_id = await get_account_id(client)
    quantity_to_buy = await calculate_purchase_quantity(client, bond, account_id)

    if quantity_to_buy > 0:
        try:
            buy_price = await buy_bond(client, account_id, bond, quantity_to_buy)
        except Exception as e:
            logger.error("An error occurred while buying the bond: %s", e)
        else:
            # calculating real_buy_price here, instead of using fee provided by api
            # itself - because in provided by api field fee is always 0 by some reason.
            real_buy_price = buy_price + bond.fee
            message = _format_purchase_notification(
                bond, quantity_to_buy, real_buy_price
            )
            logger.info(message)
            try:
                await send_telegram_message(message)
            except ClientError as e:
                logger.error("An error occurred while sending telegram message: %s", e)
    else:
        logger.info(
            "Skipped bond %s: Calculated quantity is %s", bond.ticker, quantity_to_buy
        )


BOND_REFRESH_INTERVAL_HOURS = 3
BOND_REFRESH_INTERVAL_SECONDS = (60 * 60) * BOND_REFRESH_INTERVAL_HOURS


async def get_tradable_bonds(client: AsyncServices) -> list[NBond]:
    """
    Fetches and prepares a list of tradable bonds.
    """
    bonds = await fetch_bonds(client)
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    coupon_sums = await asyncio.gather(
        *[fetch_coupons_sum(client, bond) for bond in bonds]
    )
    for bond, coupon_sum in zip(bonds, coupon_sums):
        bond.coupons_sum = coupon_sum

    return bonds


async def _handle_market_data_stream(client: AsyncServices, bonds: list[NBond]) -> None:
    """
    Handles the market data stream for a list of bonds.
    """
    figi_to_bond_map = {b.figi: b for b in bonds}

    async def request_iterator():
        yield MarketDataRequest(
            subscribe_order_book_request=SubscribeOrderBookRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[OrderBookInstrument(figi=b.figi, depth=1) for b in bonds],
            )
        )
        while True:
            await asyncio.sleep(1)

    logger.info(f"Subscribed to %s bonds", len(bonds))

    loop = asyncio.get_event_loop()
    last_update_time = loop.time()
    try:
        async for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if loop.time() - last_update_time > BOND_REFRESH_INTERVAL_SECONDS:
                logger.info("Bonds update interval reached. Re-fetching...")
                break

            if not marketdata.orderbook:
                logger.info("Skipped marketdata - Got no orderbook")
                continue

            bond = figi_to_bond_map.get(marketdata.orderbook.figi)
            if not bond:
                logger.debug(
                    "Skipped update for bond %s (figi) - Not in the list",
                    marketdata.orderbook.figi,
                )
                continue

            old_price = bond.real_price
            bond.orderbook = marketdata.orderbook

            # if price changed
            if old_price != bond.real_price:
                await process_bond_for_purchase(client, bond)
    except RequestError as e:
        logger.error("Error during market data stream: %s", e)


async def start_market_streaming_session() -> None:
    """
    Starts the main market streaming session.
    """
    while True:
        async with AsyncClient(settings.TINVEST_TOKEN) as client:
            bonds = await get_tradable_bonds(client)
            await _handle_market_data_stream(client, bonds)
