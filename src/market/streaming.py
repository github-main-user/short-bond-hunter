import logging
import time

from tinkoff.invest import (
    Client,
    MarketDataRequest,
    OrderBookInstrument,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)

from src.config import settings
from src.market.schemas import NBond
from src.market.services import (
    buy_bond,
    fetch_bonds,
    get_account_balance,
    get_account_id,
    get_existing_bonds,
)
from src.market.utils import filter_bonds, normalize_quotation
from src.telegram.services import send_telegram_message

logger = logging.getLogger(__name__)


def trading_logic(bond: NBond) -> None:
    logger.info("Processing bond: %s", bond.ticker)

    if not bond.market_data:
        logger.info("Skipped bond: %s - No market data", bond.ticker)
        return

    if not (
        settings.ANNUAL_YIELD_MIN
        <= bond.market_data.annual_yield
        <= settings.ANNUAL_YIELD_MAX
    ):
        logger.info(
            "Skipped %s - Annual yield (%s%%) is not in allowed range (%s%%, %s%%)",
            bond.ticker,
            format(bond.market_data.annual_yield, ".2f"),
            settings.ANNUAL_YIELD_MIN,
            settings.ANNUAL_YIELD_MAX,
        )
        return

    logger.info(
        f"Trying to buy bond: `%s` (%s%%) (%s bonds for current: %s₽, real: %s₽)",
        bond.ticker,
        format(bond.market_data.annual_yield, ".2f"),
        bond.market_data.ask_quantity,
        format(bond.market_data.current_price, ".2f"),
        format(bond.market_data.real_price, ".2f"),
    )
    if bond.market_data.real_price <= 0:
        logger.info("Skipped bond: %s - real_price is not positive.", bond.ticker)
        return

    account_id = get_account_id()
    balance = get_account_balance(account_id)
    existing_bond = get_existing_bonds(account_id).get(bond.ticker)

    quantity_to_buy_single = int(
        settings.BOND_SUM_MAX_SINGLE // bond.market_data.real_price
    )

    if existing_bond:
        current_value = normalize_quotation(
            existing_bond.quantity
        ) * normalize_quotation(existing_bond.current_price)
        allowed_budget = settings.BOND_SUM_MAX - current_value
    else:
        allowed_budget = settings.BOND_SUM_MAX

    quantity_allowed_to_buy = 0
    if allowed_budget > 0:
        quantity_allowed_to_buy = int(allowed_budget // bond.market_data.real_price)

    quantity_available_to_buy = int(balance // bond.market_data.real_price)

    quantity_to_buy = min(
        quantity_to_buy_single,
        quantity_allowed_to_buy,
        quantity_available_to_buy,
        bond.market_data.ask_quantity,
    )

    if quantity_to_buy > 0:
        try:
            buy_price = buy_bond(account_id, bond, quantity_to_buy)
        except Exception as e:
            logger.error("Error occurred during order post %s", e)
        else:
            real_buy_price = buy_price + bond.market_data.fee
            message = (
                f"Bought {quantity_to_buy} of {bond.ticker} ({bond.market_data.annual_yield:.2f}%)\n"
                f"Available: {bond.market_data.ask_quantity}\n"
                f"Expected price: {bond.market_data.real_price * quantity_to_buy:.2f}₽\n"
                f"Actual price: {real_buy_price:.2f}₽\n"
                f"Benefit: {bond.market_data.benefit:.2f}₽ in {bond.days_to_maturity} days ({bond.market_data.benefit / bond.days_to_maturity:.2f}₽ per day)"
            )
            logger.info(message)
            send_telegram_message(message)
    else:
        logger.info(
            "Skipped buying %s: calculated quantity is %s",
            bond.ticker,
            quantity_to_buy,
        )


def run_streaming_logic():
    bonds = fetch_bonds()
    logger.info("Got %s bonds", len(bonds))

    bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
    logger.info("%s bonds left after filtration", len(bonds))

    figi_to_bond_map = {b.figi: b for b in bonds}

    def request_iterator():
        yield MarketDataRequest(
            subscribe_order_book_request=SubscribeOrderBookRequest(
                subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                instruments=[OrderBookInstrument(figi=b.figi, depth=1) for b in bonds],
            )
        )
        while True:
            time.sleep(1)

    logger.info(f"Subscribed to {len(bonds)} bonds")
    with Client(settings.TINVEST_TOKEN) as client:
        for marketdata in client.market_data_stream.market_data_stream(
            request_iterator()
        ):
            if not marketdata.orderbook:
                logger.info("Skipping marketdata - Got no orderbook")
                continue

            bond = figi_to_bond_map[marketdata.orderbook.figi]

            old_price = bond.market_data.real_price if bond.market_data else None
            bond.update_market_data(marketdata.orderbook, settings.FEE_PERCENT)

            # if price changed
            if bond.market_data and old_price != bond.market_data.real_price:
                trading_logic(bond)
