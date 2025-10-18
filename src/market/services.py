from datetime import datetime, timezone

from tinkoff.invest import Client

from src.config import settings
from src.market.utils import normalize_quotation

from .schemas import MarketData, NBond


def fetch_bonds() -> list[NBond]:
    with Client(settings.TINVEST_TOKEN) as client:
        response = client.instruments.bonds()
        return [NBond.from_bond(bond) for bond in response.instruments]


def update_market_data(fee_percent: float, bond: NBond) -> None:
    market_data = MarketData()
    market_data.fee_percent = fee_percent

    now = datetime.now(tz=timezone.utc)
    with Client(settings.TINVEST_TOKEN) as client:
        coupon_resp = client.instruments.get_bond_coupons(
            figi=bond.figi,
            from_=now,
            to=bond.maturity_date,
        )
        orderbook_resp = client.market_data.get_order_book(figi=bond.figi, depth=1)

        if not orderbook_resp.asks:
            raise ValueError(f"No asks available in orderbook for {bond.ticker}")

    # Sum coupon payments normalized
    market_data.coupons_sum = sum(
        normalize_quotation(c.pay_one_bond) for c in coupon_resp.events
    )

    # Normalize price from % to absolute value
    ask_price_percent = normalize_quotation(orderbook_resp.asks[0].price)
    market_data.ask_quantity = orderbook_resp.asks[0].quantity
    market_data.current_price = (bond.nominal * ask_price_percent) / 100

    # Calculate fee and real price including accrued coupon interest and fee
    market_data.fee = market_data.current_price * (market_data.fee_percent / 100)
    market_data.real_price = (
        market_data.current_price + bond.aci_value + market_data.fee
    )

    # Calculate total expected return (nominal + coupons)
    market_data.full_return = bond.nominal + market_data.coupons_sum

    days_to_maturity = max((bond.maturity_date - now).days, 1)

    market_data.benefit = market_data.full_return - market_data.real_price

    # Annualized yield as percentage
    market_data.annual_yield = (
        (market_data.benefit / market_data.real_price)
        * (365.25 / days_to_maturity)
        * 100
    )

    bond.market_data = market_data
