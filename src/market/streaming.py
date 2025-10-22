import logging
import time

from tinkoff.invest import (
    Client,
    MarketDataRequest,
    OrderBookInstrument,
    RequestError,
    SubscribeOrderBookRequest,
    SubscriptionAction,
)

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


def trading_logic(bond: NBond) -> None:
    logger.info("Processing bond: %s", bond.ticker)

    if not (
        settings.ANNUAL_YIELD_MIN <= bond.annual_yield <= settings.ANNUAL_YIELD_MAX
    ):
        logger.info(
            "Skipped %s - Annual yield (%s%%) is not in allowed range (%s%%, %s%%)",
            bond.ticker,
            format(bond.annual_yield, ".2f"),
            settings.ANNUAL_YIELD_MIN,
            settings.ANNUAL_YIELD_MAX,
        )
        return

    logger.info(
        f"Trying to buy bond: `%s` (%s%%) (%s bonds for current: %s₽, real: %s₽)",
        bond.ticker,
        format(bond.annual_yield, ".2f"),
        bond.ask_quantity,
        format(bond.current_price, ".2f"),
        format(bond.real_price, ".2f"),
    )
    if bond.real_price <= 0:
        logger.info("Skipped bond: %s - real_price is not positive.", bond.ticker)
        return

    account_id = get_account_id()
    balance = get_account_balance(account_id)
    existing_bond = get_existing_bonds(account_id).get(bond.ticker)

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

    quantity_to_buy = min(
        quantity_to_buy_single,
        quantity_allowed_to_buy,
        quantity_available_to_buy,
        bond.ask_quantity,
    )

    if quantity_to_buy > 0:
        try:
            buy_price = buy_bond(account_id, bond, quantity_to_buy)
        except Exception as e:
            logger.error("Error occurred during order post %s", e)
        else:
            real_buy_price = buy_price + bond.fee
            message = (
                f"Bought {quantity_to_buy} of {bond.ticker} ({bond.annual_yield:.2f}%)\n"
                f"Available: {bond.ask_quantity}\n"
                f"Expected price: {bond.real_price * quantity_to_buy:.2f}₽\n"
                f"Actual price: {real_buy_price:.2f}₽\n"
                f"Benefit per 1: {bond.benefit:.2f}₽ in {bond.days_to_maturity} days ({bond.benefit / bond.days_to_maturity:.2f}₽ per day)"
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
    update_interval_seconds = 60 * 60  # 1 hour

    while True:
        bonds = fetch_bonds()
        logger.info("Got %s bonds", len(bonds))

        bonds = filter_bonds(bonds, maximum_days=settings.DAYS_TO_MATURITY_MAX)
        logger.info("%s bonds left after filtration", len(bonds))

        for bond in bonds:
            bond.coupons_sum = fetch_coupons_sum(bond)

        figi_to_bond_map = {b.figi: b for b in bonds}

        def request_iterator():
            yield MarketDataRequest(
                subscribe_order_book_request=SubscribeOrderBookRequest(
                    subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                    instruments=[
                        OrderBookInstrument(figi=b.figi, depth=1) for b in bonds
                    ],
                )
            )
            while True:
                time.sleep(1)

        logger.info(f"Subscribed to {len(bonds)} bonds")

        last_update_time = time.time()
        try:
            with Client(settings.TINVEST_TOKEN) as client:
                for marketdata in client.market_data_stream.market_data_stream(
                    request_iterator()
                ):
                    if time.time() - last_update_time > update_interval_seconds:
                        logger.info("Bonds update interval reached. Re-fetching...")
                        break

                    if not marketdata.orderbook:
                        logger.info("Skipping marketdata - Got no orderbook")
                        continue

                    bond = figi_to_bond_map.get(marketdata.orderbook.figi)
                    if not bond:
                        logger.debug(
                            "Skipping update for bond not in the list: %s",
                            marketdata.orderbook.figi,
                        )
                        continue

                    old_price = bond.real_price
                    bond.orderbook = marketdata.orderbook

                    # if price changed
                    if old_price != bond.real_price:
                        trading_logic(bond)
        except RequestError as e:
            logging.error("Error during market data stream: %s", e)
